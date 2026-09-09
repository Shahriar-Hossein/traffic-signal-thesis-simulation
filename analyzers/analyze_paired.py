"""
Analyze paired replay runs (data/paired/{plan_id}/).

Deliberately separate from analyze_log.py and analyze_count_log.py, which own
data/logs/** and data/logs_by_count/** respectively.  Nothing here reads or
writes either of those roots, and neither of them walks data/paired.

Two things happen, in this order:

  1. A validity gate.  Both arms must have completed, crossed every planned
     vehicle, and honoured the plan comparably — same frame rate, same release
     drift.  Physics runs inside the renderer, so an arm that rendered slower
     had slower vehicles, and that confound is indistinguishable from a
     controller effect.  A pair that fails the gate is reported as invalid,
     never quietly averaged in.
  2. The paired comparison itself.  Vehicle `plan_seq = k` in one arm and
     `plan_seq = k` in another are the *same arrival*, so their two wait times
     form a descriptive matched difference. Inference uses independent plans,
     because vehicles within an approach interact.

    python3 analyzers/analyze_paired.py data/paired/even_500_seed07
    python3 analyzers/analyze_paired.py --batch data/paired
"""

import argparse
import csv
import glob
import json
import math
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.plan import load_plan
from core.provenance import fingerprint
from collections import defaultdict

BASE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
PAIRED_ROOT = os.path.join(BASE_DIR, "paired")

# Starting tolerances for the validity gate.  These are guesses until §9.5 of
# docs/PAIRED_REPLAY_PLAN.md has been measured on the target machine; tighten
# or loosen them from what that actually shows.
DEFAULT_FPS_TOLERANCE = 0.05        # relative spread in fps_mean across arms
DEFAULT_DRIFT_TOLERANCE_MS = 250.0  # worst single release lateness, per arm

# Below this many matched pairs the normal approximation in the signed-rank
# test is not trustworthy and the p-value is reported as None.
MIN_PAIRS_FOR_TEST = 10


# --- Reading one arm -----------------------------------------------------

def read_csv_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _load_arm(arm_dir):
    """Load one arm's vehicle log, signal log and metadata sidecar."""
    arm = os.path.basename(arm_dir.rstrip(os.sep))

    # Sidecar logs live beside the vehicle log and share its stem, so match
    # by suffix rather than by substring.
    logs = [
        p for p in sorted(glob.glob(os.path.join(arm_dir, "*.csv")))
        if not p.endswith(("_signal.csv", "_phases.csv"))
    ]
    if not logs:
        return {"arm": arm, "error": "no vehicle log found"}
    if len(logs) > 1:
        # One run per process, one run per arm folder.  More than one log here
        # means two runs were written into the same arm and the pairing is
        # ambiguous — refuse rather than pick.
        return {
            "arm": arm,
            "error": f"{len(logs)} vehicle logs in the arm folder, expected 1",
        }

    log_path = logs[0]
    meta_path = log_path.replace(".csv", "_meta.json")
    signal_path = log_path.replace(".csv", "_signal.csv")

    meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
        except (OSError, ValueError) as e:
            return {"arm": arm, "error": f"could not read {os.path.basename(meta_path)}: {e}"}

    signal_changes = 0
    if os.path.exists(signal_path):
        signal_changes = len(read_csv_rows(signal_path))

    phase_path = log_path.replace(".csv", "_phases.csv")
    return {
        "arm": arm,
        "log_path": log_path,
        "rows": read_csv_rows(log_path),
        "meta": meta,
        "signal_changes": signal_changes,
        "phases": read_csv_rows(phase_path) if os.path.exists(phase_path) else [],
    }


def load_arm(arm_dir):
    try:
        return _load_arm(arm_dir)
    except (OSError, ValueError, csv.Error) as error:
        return {'arm': os.path.basename(arm_dir), 'error': f'cannot read arm: {error}'}


def percentile(values, q):
    """Nearest-rank percentile; no numpy dependency for one number."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(q * len(ordered)) - 1)
    return ordered[index]


def summarize_arm(arm):
    """Per-arm headline numbers — the part the existing analyzers already give."""
    rows = arm["rows"]
    meta = arm["meta"]

    waits = []
    travels = []
    by_direction = defaultdict(list)
    by_type = defaultdict(list)

    for row in rows:
        try:
            wait = float(row["wait_time_sec"])
        except (KeyError, TypeError, ValueError):
            continue
        waits.append(wait)
        by_direction[row["direction"]].append(wait)
        by_type[row["vehicle_type"]].append(wait)
        # Entry to stop line. Spawn distance depends on the queue ahead, so
        # this is reported next to stopped delay rather than folded into it.
        try:
            travels.append(float(row["crossed_sec"]) - float(row["released_sec"]))
        except (KeyError, TypeError, ValueError):
            pass

    direction_means = {
        d: statistics.fmean(v) for d, v in by_direction.items() if v
    }
    worst_direction = (
        max(direction_means, key=direction_means.get) if direction_means else None
    )

    duration = meta.get("duration_sec")
    clearance = meta.get("last_crossing_sec") or duration

    return {
        "controller": meta.get("controller"),
        "duration_sec": duration,
        "vehicles_logged": len(rows),
        "wait_mean": round(statistics.fmean(waits), 2) if waits else None,
        "wait_median": round(statistics.median(waits), 2) if waits else None,
        "wait_p90": round(percentile(waits, 0.90), 2) if waits else None,
        # Tail delay and the worst-served approach are the safeguards: a mean
        # gain paid for by one starved approach is not an improvement.
        "wait_p95": round(percentile(waits, 0.95), 2) if waits else None,
        "wait_max": round(max(waits), 2) if waits else None,
        "worst_direction": worst_direction,
        "worst_direction_wait_mean": round(direction_means[worst_direction], 2) if worst_direction else None,
        # Spread between the best- and worst-served approach.
        "direction_service_gap": (
            round(max(direction_means.values()) - min(direction_means.values()), 2)
            if direction_means else None
        ),
        "travel_mean": round(statistics.fmean(travels), 2) if travels else None,
        "travel_p90": round(percentile(travels, 0.90), 2) if travels else None,
        # Clearance is measured to the last crossing; duration_sec also
        # covers the display drain that follows it.
        "last_crossing_sec": meta.get("last_crossing_sec"),
        # Finite-workload clearance rate, a transformation of clearance time,
        # not a separate capacity estimate.
        "throughput_per_min": (
            round(len(rows) / clearance * 60, 2) if clearance else None
        ),
        "wait_mean_by_direction": {
            d: round(statistics.fmean(v), 2) for d, v in sorted(by_direction.items())
        },
        "wait_mean_by_type": {
            t: round(statistics.fmean(v), 2) for t, v in sorted(by_type.items())
        },
        "signal_changes": arm["signal_changes"],
        "fps_mean": meta.get("fps_mean"),
        "fps_min": meta.get("fps_min"),
        "fps_windows_recorded": len(meta.get("fps_windows") or []),
        "release_drift_mean_ms": meta.get("release_drift_mean_ms"),
        "release_drift_max_ms": meta.get("release_drift_max_ms"),
        "stop_reason": meta.get("stop_reason"),
    }


# --- Validity gate -------------------------------------------------------

def finite_number(value, positive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value > 0 if positive else value >= 0))


def check_validity(arms, plan, fps_tolerance, drift_tolerance_ms):
    """Fail closed: only a complete, attributable replay can be compared."""
    reasons = []
    if not finite_number(fps_tolerance) or not finite_number(drift_tolerance_ms):
        return ["gate tolerances must be finite and nonnegative"]
    if not isinstance(plan, dict):
        return ["verified plan is required"]
    header = plan['header']
    expected = {record['seq']: record for record in plan['vehicles']}
    n = header['target_vehicle_count']
    fps_values = []
    worst_fps = []
    hashes = {'configuration_hash': set(), 'source_hash': set()}
    for arm in arms:
        name = arm['arm']
        if arm.get('error'):
            reasons.append(f"{name}: {arm['error']}")
            continue
        meta = arm.get('meta')
        if not isinstance(meta, dict) or not meta:
            reasons.append(f"{name}: missing or invalid metadata")
            continue
        identity = {
            'generation_source': 'plan', 'run_mode': 'vehicles',
            'stop_reason': 'target_reached', 'plan_id': header['plan_id'],
            'plan_hash': header['content_hash'], 'arm': name,
            'uneven_mode': header['uneven_mode'], 'provenance_version': 1,
            'vehicle_log': os.path.basename(arm['log_path']),
            'signal_log': os.path.basename(arm['log_path']).replace('.csv', '_signal.csv'),
        }
        for key, value in identity.items():
            if meta.get(key) != value:
                reasons.append(f"{name}: {key} missing or mismatched")
        if meta.get('controller') not in ('fixed', 'priority', 'fairness_priority'):
            reasons.append(f"{name}: missing or unknown controller")
        for key in ('started_at', 'ended_at', 'plan_path'):
            if not isinstance(meta.get(key), str) or not meta[key]:
                reasons.append(f"{name}: {key} missing or invalid")
        for key in ('vehicles_planned', 'target_vehicle_count', 'vehicles_released',
                    'vehicles_generated', 'vehicles_crossed'):
            if type(meta.get(key)) is not int or meta[key] != n:
                reasons.append(f"{name}: {key} must equal planned count {n}")
        for key in ('duration_sec', 'last_crossing_sec', 'fps_mean', 'fps_min', 'frames_total',
                    'release_drift_mean_ms', 'release_drift_max_ms'):
            if not finite_number(meta.get(key), positive=not key.startswith('release_')):
                reasons.append(f"{name}: {key} missing, nonfinite or out of range")
        windows = meta.get('fps_windows')
        if (not isinstance(windows, list) or not windows
                or not all(finite_number(value, positive=True) for value in windows)):
            reasons.append(f"{name}: fps_windows missing or invalid")
        elif not finite_number(meta.get('fps_window_sec'), positive=True):
            reasons.append(f"{name}: fps_window_sec missing or invalid")
        elif meta.get('fps_min') != min(windows):
            reasons.append(f"{name}: fps_min does not match the recorded windows")
        if finite_number(meta.get('fps_mean'), positive=True):
            fps_values.append(meta['fps_mean'])
        if finite_number(meta.get('fps_min'), positive=True):
            worst_fps.append(meta['fps_min'])
        if (finite_number(meta.get('last_crossing_sec'), positive=True)
                and finite_number(meta.get('duration_sec'), positive=True)
                and meta['last_crossing_sec'] > meta['duration_sec']):
            reasons.append(f"{name}: last crossing falls after the run ended")
        drift = meta.get('release_drift_max_ms')
        if finite_number(drift) and drift > drift_tolerance_ms:
            reasons.append(f"{name}: release_drift_max_ms={drift} exceeds {drift_tolerance_ms}")
        mean_drift = meta.get('release_drift_mean_ms')
        if finite_number(mean_drift) and finite_number(drift) and mean_drift > drift:
            reasons.append(f"{name}: mean release drift exceeds maximum")
        for payload, key in (('configuration', 'configuration_hash'), ('source_files', 'source_hash')):
            value = meta.get(payload)
            try:
                matches = isinstance(value, dict) and bool(value) and fingerprint(value) == meta.get(key)
            except (ValueError, TypeError):
                matches = False
            if not matches:
                reasons.append(f"{name}: {payload} missing or fingerprint mismatch")
            else:
                hashes[key].add(meta[key])
        if not arm.get('signal_changes'):
            reasons.append(f"{name}: no signal changes recorded")
        rows = arm['rows']
        if len(rows) != n:
            reasons.append(f"{name}: logged {len(rows)} crossings, expected {n}")
        seen = set()
        for index, row in enumerate(rows):
            try:
                key = int(row.get('plan_seq', ''))
            except (TypeError, ValueError):
                reasons.append(f"{name}: row {index} has missing or invalid plan_seq")
                continue
            if key in seen:
                reasons.append(f"{name}: duplicate plan_seq {key}")
            seen.add(key)
            record = expected.get(key)
            if record is None:
                reasons.append(f"{name}: unexpected plan_seq {key}")
                continue
            for attribute in ('vehicle_type', 'direction', 'lane', 'will_turn',
                              'turn_direction', 'target_turn_lane'):
                if row.get(attribute) != str(record[attribute]):
                    reasons.append(f"{name}: seq {key} {attribute} differs from plan")
            if row.get('mode') != meta.get('controller'):
                reasons.append(f"{name}: seq {key} controller differs from metadata")
            try:
                wait = float(row['wait_time_sec'])
            except (KeyError, TypeError, ValueError):
                wait = None
            if not finite_number(wait):
                reasons.append(f"{name}: seq {key} wait must be finite and nonnegative")
            times = {}
            for column in ('released_sec', 'crossed_sec'):
                try:
                    times[column] = float(row[column])
                except (KeyError, TypeError, ValueError):
                    times[column] = None
                if not finite_number(times[column]):
                    reasons.append(f"{name}: seq {key} {column} must be finite and nonnegative")
            if all(value is not None for value in times.values()):
                if times['crossed_sec'] < times['released_sec']:
                    reasons.append(f"{name}: seq {key} crossed before it was released")
                if times['released_sec'] + 0.001 < record['t_offset_sec']:
                    reasons.append(f"{name}: seq {key} released before its planned offset")
        missing = sorted(set(expected) - seen)
        if missing:
            reasons.append(f"{name}: missing {len(missing)} planned crossings (first IDs: {missing[:20]})")
    for key, values in hashes.items():
        if len(values) > 1:
            reasons.append(f"{key} differs across arms")
    # Both the average and the worst window must agree: two arms can share a
    # mean frame rate and still have stalled at different moments.
    for label, values in (('fps_mean', fps_values), ('fps_min', worst_fps)):
        if len(values) == len(arms) and values:
            spread = (max(values) - min(values)) / max(values)
            if spread > fps_tolerance:
                reasons.append(f"{label} spread {spread:.1%} exceeds {fps_tolerance:.1%}")
    return reasons


# --- Interval estimation -------------------------------------------------

BOOTSTRAP_ITERATIONS = 10000
BOOTSTRAP_SEED = 20260910


def bootstrap_ci(values, confidence=0.95, iterations=BOOTSTRAP_ITERATIONS):
    """
    Percentile bootstrap CI for the mean of independent plan-level effects.

    Bootstrapped rather than assumed normal: the number of plans is small and
    the shape of the effect distribution is not established. The seed is fixed
    so a reported interval can be reproduced exactly.
    """
    values = list(values)
    if len(values) < 2:
        return {"ci_low": None, "ci_high": None, "ci_method": "insufficient plans",
                "ci_confidence": confidence}

    generator = random.Random(BOOTSTRAP_SEED)
    n = len(values)
    means = sorted(
        statistics.fmean(values[generator.randrange(n)] for _ in range(n))
        for _ in range(iterations)
    )
    tail = (1 - confidence) / 2
    low = means[max(0, math.ceil(tail * iterations) - 1)]
    high = means[min(iterations - 1, math.ceil((1 - tail) * iterations) - 1)]
    return {
        "ci_low": round(low, 3),
        "ci_high": round(high, 3),
        "ci_method": f"percentile bootstrap, {iterations} resamples, seed {BOOTSTRAP_SEED}",
        "ci_confidence": confidence,
    }


def contrast_summary(means):
    """Plan-level effect summary: the unit of inference is the plan."""
    return {
        "plans": len(means),
        "delta_wait_mean_of_plan_means": round(statistics.fmean(means), 3),
        "delta_wait_median_of_plan_means": round(statistics.median(means), 3),
        "delta_wait_sd_of_plan_means": (
            round(statistics.stdev(means), 3) if len(means) > 1 else None
        ),
        "plans_favouring_arm": sum(1 for m in means if m < 0),
        **bootstrap_ci(means),
        **{f"wilcoxon_{k}": v for k, v in wilcoxon_signed_rank(means).items()},
    }


# --- Signed-rank test ----------------------------------------------------

def normal_sf(z):
    """Upper-tail probability of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def wilcoxon_signed_rank(deltas):
    """
    Two-sided Wilcoxon signed-rank test, normal approximation with tie and
    continuity corrections.

    Written out rather than imported so the analyzer has no scipy dependency;
    at the pair sizes this design produces (hundreds of vehicles) the normal
    approximation is what scipy would use anyway.  Returns None for `p` when
    there are too few non-zero differences to trust it.
    """
    nonzero = [d for d in deltas if d != 0]
    n = len(nonzero)
    if n == 0:
        return {"n_nonzero": 0, "w_statistic": None, "z": None, "p_value": None}

    # Average ranks over ties in |d|
    ordered = sorted(range(n), key=lambda i: abs(nonzero[i]))
    ranks = [0.0] * n
    tie_correction = 0
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(nonzero[ordered[j + 1]]) == abs(nonzero[ordered[i]]):
            j += 1
        average_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[ordered[k]] = average_rank
        group = j - i + 1
        tie_correction += group ** 3 - group
        i = j + 1

    w_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    w_minus = sum(r for r, d in zip(ranks, nonzero) if d < 0)
    w = min(w_plus, w_minus)

    if n < MIN_PAIRS_FOR_TEST:
        return {"n_nonzero": n, "w_statistic": w, "z": None, "p_value": None}

    mean = n * (n + 1) / 4
    variance = (n * (n + 1) * (2 * n + 1) - tie_correction / 2) / 24
    if variance <= 0:
        return {"n_nonzero": n, "w_statistic": w, "z": None, "p_value": None}

    z = (w - mean + 0.5) / math.sqrt(variance)   # continuity correction
    p = min(1.0, 2 * normal_sf(abs(z)))

    return {
        "n_nonzero": n,
        "w_statistic": w,
        "z": round(z, 4),
        "p_value": p,
    }


# --- Pairing -------------------------------------------------------------

def waits_by_seq(arm):
    """Map plan_seq -> wait time, and note rows that carry no pairing key."""
    mapping = {}
    unkeyed = 0
    for row in arm["rows"]:
        key = row.get("plan_seq")
        if key is None or key == "":
            unkeyed += 1
            continue
        try:
            mapping[int(key)] = float(row["wait_time_sec"])
        except (TypeError, ValueError):
            unkeyed += 1
    return mapping, unkeyed


def compare_arms(baseline, other):
    """
    Per-vehicle Δwait between two arms, joined on plan_seq.

    Negative Δ means `other` waited less than `baseline` for that same arrival.
    """
    base_waits, base_unkeyed = waits_by_seq(baseline)
    other_waits, other_unkeyed = waits_by_seq(other)

    shared = sorted(set(base_waits) & set(other_waits))
    # A plan_seq present in one arm and missing from the other means that
    # vehicle never crossed there.  It cannot be paired, and silently dropping
    # it would bias the comparison toward whichever arm lost the vehicle.
    only_baseline = sorted(set(base_waits) - set(other_waits))
    only_other = sorted(set(other_waits) - set(base_waits))

    deltas = [other_waits[k] - base_waits[k] for k in shared]
    wins = sum(1 for d in deltas if d < 0)
    ties = sum(1 for d in deltas if d == 0)

    result = {
        "baseline": baseline["arm"],
        "arm": other["arm"],
        "n_matched": len(shared),
        "unmatched_in_baseline": len(only_baseline),
        "unmatched_in_arm": len(only_other),
        "rows_without_plan_seq": base_unkeyed + other_unkeyed,
        "delta_wait_mean": round(statistics.fmean(deltas), 3) if deltas else None,
        "delta_wait_median": round(statistics.median(deltas), 3) if deltas else None,
        f"win_rate_{other['arm']}": round(wins / len(deltas), 4) if deltas else None,
        "tied": ties,
    }
    # Vehicles interact within a plan; no inferential vehicle-level p-value.
    result['inference_unit'] = 'plan'
    result['wilcoxon_p_value'] = None

    if only_baseline or only_other:
        result["unmatched_plan_seqs"] = {
            baseline["arm"]: only_baseline[:20],
            other["arm"]: only_other[:20],
        }

    return result


# --- Whole-pair analysis -------------------------------------------------

def arm_sort_key(arm):
    """
    Order arms by when they actually ran.

    The driver runs arms in the order the user listed them, so run order is
    the user's order — and the first arm is the one they meant as the
    baseline.  Sorting the folder names alphabetically instead would silently
    make `fairness_priority` the baseline in `--arms fixed priority
    fairness_priority`, and every delta would be reported against the wrong
    reference.  Falls back to the arm name when a sidecar is missing.
    """
    meta = arm.get("meta")
    started_at = meta.get("started_at") if isinstance(meta, dict) else None
    if not isinstance(started_at, str):
        started_at = None
    return (started_at is None, started_at or "", arm["arm"])


def analyze_pair(plan_dir, fps_tolerance=DEFAULT_FPS_TOLERANCE,
                 drift_tolerance_ms=DEFAULT_DRIFT_TOLERANCE_MS, write=True,
                 baseline=None):
    """Analyze one data/paired/{plan_id}/ folder and return its comparison dict."""
    plan_dir = os.path.abspath(plan_dir)
    plan_id = os.path.basename(plan_dir.rstrip(os.sep))

    plan = None
    plan_errors = []
    planned_count = None
    try:
        plan = load_plan(os.path.join(plan_dir, 'plan.json'))
        plan_id = plan['header']['plan_id']
        planned_count = plan['header']['target_vehicle_count']
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        plan_errors.append(f"cannot verify plan.json: {error}")

    arm_dirs = sorted(
        os.path.join(plan_dir, name) for name in os.listdir(plan_dir)
        if os.path.isdir(os.path.join(plan_dir, name))
    )
    arms = sorted((load_arm(d) for d in arm_dirs), key=arm_sort_key)

    if baseline is not None:
        # An explicit baseline wins over run order.
        arms.sort(key=lambda a: a["arm"] != baseline)

    header = plan['header'] if plan else {}
    comparison = {
        "plan_id": plan_id,
        # The stratum this plan belongs to. Effects are reported per scenario
        # because a mean pooled across demand regimes describes none of them.
        "scenario": (
            f"{header.get('uneven_mode')}_{header.get('target_vehicle_count')}"
            if plan else "unknown"
        ),
        "planned_vehicle_count": planned_count,
        "arm_names": [a["arm"] for a in arms],
    }

    reasons = plan_errors + check_validity(arms, plan, fps_tolerance, drift_tolerance_ms)
    if baseline is not None and baseline not in comparison['arm_names']:
        reasons.append(f"requested baseline {baseline!r} is missing")
    if len(arms) < 2:
        reasons.append(f"found {len(arms)} arms; at least 2 required")
    comparison["valid"] = not reasons
    comparison["invalid_reasons"] = reasons

    comparison["arms"] = {
        a["arm"]: summarize_arm(a) for a in arms if not reasons and not a.get("error")
    }

    # Every other arm is compared against the first, so K arms produce K-1
    # matched comparisons rather than assuming there are exactly two.
    usable = [a for a in arms if not reasons and not a.get("error")]
    baseline_arm = usable[0] if usable else None
    comparison["baseline_arm"] = baseline_arm["arm"] if baseline_arm else None
    comparison["paired"] = [
        compare_arms(baseline_arm, other) for other in usable[1:]
    ] if baseline_arm else []

    if write:
        write_comparison(plan_dir, comparison)
    return comparison


def write_comparison(plan_dir, comparison):
    """comparison.json is written here and by the driver — never by the simulation."""
    path = os.path.join(plan_dir, "comparison.json")
    with open(path, "w") as f:
        json.dump(comparison, f, indent=2, allow_nan=False)
        f.write("\n")
    return path


# --- Batch ---------------------------------------------------------------

def analyze_batch(root, fps_tolerance=DEFAULT_FPS_TOLERANCE,
                  drift_tolerance_ms=DEFAULT_DRIFT_TOLERANCE_MS, write=True,
                  baseline=None):
    """Analyze every plan folder under `root` and aggregate across pairs."""
    plan_dirs = sorted(
        os.path.join(root, name) for name in os.listdir(root)
        if os.path.isdir(os.path.join(root, name))
    )

    pairs = [
        analyze_pair(d, fps_tolerance, drift_tolerance_ms, write=write,
                     baseline=baseline)
        for d in plan_dirs
    ]
    valid = [p for p in pairs if p.get("valid")]

    # One mean difference per plan; never pool interacting vehicles as replicates.
    pooled = defaultdict(list)
    stratified = defaultdict(lambda: defaultdict(list))
    for pair in valid:
        for block in pair.get("paired", []):
            key = f"{block['baseline']}_vs_{block['arm']}"
            if block["delta_wait_mean"] is not None:
                pooled[key].append(block["delta_wait_mean"])
                stratified[pair.get("scenario", "unknown")][key].append(
                    block["delta_wait_mean"])

    invalid_by_scenario = defaultdict(int)
    for pair in pairs:
        if not pair.get("valid"):
            invalid_by_scenario[pair.get("scenario", "unknown")] += 1

    aggregate = {
        "root": os.path.abspath(root),
        "plans_total": len(pairs),
        "plans_valid": len(valid),
        "plans_invalid": [
            {"plan_id": p["plan_id"], "reasons": p["invalid_reasons"]}
            for p in pairs if not p.get("valid")
        ],
        # Failures are reported by scenario, not dropped: a scenario that
        # fails often is a finding about that scenario.
        "invalid_by_scenario": dict(sorted(
            (scenario, count) for scenario, count in invalid_by_scenario.items()
        )),
        "inference_unit": "plan",
        "per_contrast": {},
        "per_scenario": {},
    }

    for key, means in pooled.items():
        aggregate["per_contrast"][key] = contrast_summary(means)

    for scenario, contrasts in sorted(stratified.items()):
        aggregate["per_scenario"][scenario] = {
            key: contrast_summary(means) for key, means in sorted(contrasts.items())
        }

    if write:
        path = os.path.join(root, "batch_comparison.json")
        with open(path, "w") as f:
            json.dump(aggregate, f, indent=2)
            f.write("\n")
        print(f"✅ Batch summary saved to: {path}")

    return aggregate


# --- Reporting -----------------------------------------------------------

def print_pair(comparison):
    print(f"\n=== {comparison['plan_id']} ===")
    if comparison.get("valid"):
        print("✅ valid pair")
    else:
        print("⛔ INVALID — reported, not averaged in:")
        for reason in comparison.get("invalid_reasons", []):
            print(f"   - {reason}")

    for name, summary in comparison.get("arms", {}).items():
        print(
            f"  {name:18} {summary['vehicles_logged']:>5} veh  "
            f"clear {str(summary['last_crossing_sec']):>8}s  "
            f"wait mean {str(summary['wait_mean']):>7}  "
            f"p95 {str(summary['wait_p95']):>7}  "
            f"worst {str(summary['worst_direction']):>5} "
            f"{str(summary['worst_direction_wait_mean']):>7}  "
            f"travel {str(summary['travel_mean']):>7}  "
            f"thr {str(summary['throughput_per_min']):>7}/min  "
            f"fps {str(summary['fps_mean']):>6}"
        )

    for block in comparison.get("paired", []):
        win_key = f"win_rate_{block['arm']}"
        p = block.get("wilcoxon_p_value")
        print(
            f"  paired {block['baseline']} -> {block['arm']}: "
            f"n={block['n_matched']} "
            f"Δwait mean {block['delta_wait_mean']} "
            f"median {block['delta_wait_median']} "
            f"win {block[win_key]} "
            f"p={'n/a' if p is None else f'{p:.2e}'}"
        )
        if block["unmatched_in_baseline"] or block["unmatched_in_arm"]:
            print(
                f"    ⚠️  unmatched plan_seq — {block['baseline']}: "
                f"{block['unmatched_in_baseline']}, {block['arm']}: "
                f"{block['unmatched_in_arm']} (a vehicle never crossed)"
            )


def print_contrasts(label, contrasts):
    for key, block in contrasts.items():
        print(
            f"  [{label}] {key}: Δwait {block['delta_wait_mean_of_plan_means']} "
            f"95% CI [{block['ci_low']}, {block['ci_high']}] "
            f"over {block['plans']} plans, "
            f"{block['plans_favouring_arm']} favouring"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("plan_dir", nargs="?", default=None,
                        help="A data/paired/{plan_id}/ folder.")
    parser.add_argument("--batch", metavar="DIR",
                        help="Analyze every plan folder under DIR and aggregate.")
    parser.add_argument("--fps-tolerance", type=float, default=DEFAULT_FPS_TOLERANCE,
                        help="Allowed relative spread in fps_mean across arms.")
    parser.add_argument("--drift-tolerance-ms", type=float,
                        default=DEFAULT_DRIFT_TOLERANCE_MS,
                        help="Allowed worst release lateness per arm.")
    parser.add_argument("--baseline",
                        help="Arm every other is compared against "
                             "(default: the arm that ran first).")
    args = parser.parse_args(argv)

    if args.batch:
        aggregate = analyze_batch(args.batch, args.fps_tolerance,
                                  args.drift_tolerance_ms, baseline=args.baseline)
        for plan_dir in sorted(
            os.path.join(args.batch, n) for n in os.listdir(args.batch)
            if os.path.isdir(os.path.join(args.batch, n))
        ):
            print_pair(analyze_pair(plan_dir, args.fps_tolerance,
                                    args.drift_tolerance_ms, write=False,
                                    baseline=args.baseline))
        print(f"\n{aggregate['plans_valid']}/{aggregate['plans_total']} plans valid")
        print_contrasts("overall", aggregate["per_contrast"])
        for scenario, contrasts in aggregate["per_scenario"].items():
            print_contrasts(scenario, contrasts)
        if aggregate["invalid_by_scenario"]:
            print("  invalid pairs by scenario: "
                  + ", ".join(f"{k}={v}" for k, v in aggregate["invalid_by_scenario"].items()))
        return

    plan_dir = args.plan_dir or PAIRED_ROOT
    if not os.path.isdir(plan_dir):
        parser.error(f"{plan_dir} is not a directory")

    comparison = analyze_pair(plan_dir, args.fps_tolerance, args.drift_tolerance_ms,
                              baseline=args.baseline)
    print_pair(comparison)
    print(f"\n✅ Written to {os.path.join(plan_dir, 'comparison.json')}")


if __name__ == "__main__":
    main()
