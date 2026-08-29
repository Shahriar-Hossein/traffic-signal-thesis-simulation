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
     form a matched pair and a signed-rank test applies.  That is the claim
     this whole design exists to support.

    python3 analyzers/analyze_paired.py data/paired/even_500_seed07
    python3 analyzers/analyze_paired.py --batch data/paired
"""

import argparse
import csv
import glob
import json
import math
import os
import statistics
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


def load_arm(arm_dir):
    """Load one arm's vehicle log, signal log and metadata sidecar."""
    arm = os.path.basename(arm_dir.rstrip(os.sep))

    logs = [
        p for p in sorted(glob.glob(os.path.join(arm_dir, "*.csv")))
        if "signal" not in os.path.basename(p)
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

    return {
        "arm": arm,
        "log_path": log_path,
        "rows": read_csv_rows(log_path),
        "meta": meta,
        "signal_changes": signal_changes,
    }


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

    duration = meta.get("duration_sec")

    return {
        "controller": meta.get("controller"),
        "duration_sec": duration,
        "vehicles_logged": len(rows),
        "wait_mean": round(statistics.fmean(waits), 2) if waits else None,
        "wait_median": round(statistics.median(waits), 2) if waits else None,
        "wait_p90": round(percentile(waits, 0.90), 2) if waits else None,
        "wait_max": round(max(waits), 2) if waits else None,
        # Throughput is the meaningful cross-arm number here: the vehicle count
        # is fixed by the plan, so a faster run is a better controller.
        "throughput_per_min": (
            round(len(rows) / duration * 60, 2) if duration else None
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
        "release_drift_mean_ms": meta.get("release_drift_mean_ms"),
        "release_drift_max_ms": meta.get("release_drift_max_ms"),
        "stop_reason": meta.get("stop_reason"),
    }


# --- Validity gate -------------------------------------------------------

def check_validity(arms, planned_count, fps_tolerance, drift_tolerance_ms):
    """Return the list of reasons this pair may not be reported. Empty = valid."""
    reasons = []

    for arm in arms:
        name = arm["arm"]
        if arm.get("error"):
            reasons.append(f"{name}: {arm['error']}")
            continue

        meta = arm["meta"]
        if not meta:
            reasons.append(f"{name}: no _meta.json, cannot verify the run completed")
            continue

        if meta.get("generation_source") != "plan":
            reasons.append(
                f"{name}: generation_source={meta.get('generation_source')!r}, "
                "this arm did not replay the plan"
            )

        if meta.get("stop_reason") != "target_reached":
            reasons.append(f"{name}: stop_reason={meta.get('stop_reason')!r}")

        if planned_count is not None:
            if meta.get("vehicles_released") not in (None, planned_count):
                reasons.append(
                    f"{name}: released {meta.get('vehicles_released')} of "
                    f"{planned_count} planned vehicles"
                )
            if len(arm["rows"]) != planned_count:
                reasons.append(
                    f"{name}: logged {len(arm['rows'])} crossings, "
                    f"expected {planned_count}"
                )

        drift = meta.get("release_drift_max_ms")
        if drift is not None and drift > drift_tolerance_ms:
            reasons.append(
                f"{name}: release_drift_max_ms={drift} exceeds "
                f"{drift_tolerance_ms}"
            )

    # Frame rate is compared *between* arms, not against an absolute floor:
    # what invalidates the comparison is one arm running its physics faster
    # than the other, whatever the absolute number was.
    fps_values = [
        a["meta"].get("fps_mean") for a in arms
        if not a.get("error") and a.get("meta", {}).get("fps_mean") is not None
    ]
    if len(fps_values) == len([a for a in arms if not a.get("error")]) and fps_values:
        spread = (max(fps_values) - min(fps_values)) / max(fps_values)
        if spread > fps_tolerance:
            reasons.append(
                f"fps_mean spread {spread:.1%} across arms exceeds "
                f"{fps_tolerance:.0%} — physics runs in the renderer, so the "
                "slower arm had slower vehicles"
            )
    elif arms:
        reasons.append("fps_mean missing for at least one arm, cannot gate on frame rate")

    return reasons


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
    result.update({f"wilcoxon_{k}": v for k, v in wilcoxon_signed_rank(deltas).items()})

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
    started_at = (arm.get("meta") or {}).get("started_at")
    return (started_at is None, started_at or "", arm["arm"])


def analyze_pair(plan_dir, fps_tolerance=DEFAULT_FPS_TOLERANCE,
                 drift_tolerance_ms=DEFAULT_DRIFT_TOLERANCE_MS, write=True,
                 baseline=None):
    """Analyze one data/paired/{plan_id}/ folder and return its comparison dict."""
    plan_dir = os.path.abspath(plan_dir)
    plan_id = os.path.basename(plan_dir.rstrip(os.sep))

    planned_count = None
    plan_path = os.path.join(plan_dir, "plan.json")
    if os.path.exists(plan_path):
        with open(plan_path) as f:
            header = json.load(f).get("header", {})
        plan_id = header.get("plan_id", plan_id)
        planned_count = header.get("target_vehicle_count")

    arm_dirs = sorted(
        os.path.join(plan_dir, name) for name in os.listdir(plan_dir)
        if os.path.isdir(os.path.join(plan_dir, name))
    )
    arms = sorted((load_arm(d) for d in arm_dirs), key=arm_sort_key)

    if baseline is not None:
        # An explicit baseline wins over run order.
        arms.sort(key=lambda a: a["arm"] != baseline)

    comparison = {
        "plan_id": plan_id,
        "planned_vehicle_count": planned_count,
        "arm_names": [a["arm"] for a in arms],
    }

    if len(arms) < 2:
        comparison["valid"] = False
        comparison["invalid_reasons"] = [
            f"found {len(arms)} arm folder(s); a pair needs at least 2"
        ]
        comparison["arms"] = {
            a["arm"]: summarize_arm(a) for a in arms if not a.get("error")
        }
        if write:
            write_comparison(plan_dir, comparison)
        return comparison

    reasons = check_validity(arms, planned_count, fps_tolerance, drift_tolerance_ms)
    comparison["valid"] = not reasons
    comparison["invalid_reasons"] = reasons

    comparison["arms"] = {
        a["arm"]: summarize_arm(a) for a in arms if not a.get("error")
    }

    # Every other arm is compared against the first, so K arms produce K-1
    # matched comparisons rather than assuming there are exactly two.
    usable = [a for a in arms if not a.get("error")]
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
        json.dump(comparison, f, indent=2)
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

    # The aggregate test pools every matched vehicle across valid plans; the
    # per-plan means are reported alongside so one dominant plan is visible.
    pooled = defaultdict(list)
    for pair in valid:
        for block in pair.get("paired", []):
            key = f"{block['baseline']}_vs_{block['arm']}"
            if block["delta_wait_mean"] is not None:
                pooled[key].append(block["delta_wait_mean"])

    aggregate = {
        "root": os.path.abspath(root),
        "plans_total": len(pairs),
        "plans_valid": len(valid),
        "plans_invalid": [
            {"plan_id": p["plan_id"], "reasons": p["invalid_reasons"]}
            for p in pairs if not p.get("valid")
        ],
        "per_contrast": {},
    }

    for key, means in pooled.items():
        test = wilcoxon_signed_rank(means)
        aggregate["per_contrast"][key] = {
            "plans": len(means),
            "delta_wait_mean_of_plan_means": round(statistics.fmean(means), 3),
            "delta_wait_median_of_plan_means": round(statistics.median(means), 3),
            "plans_favouring_arm": sum(1 for m in means if m < 0),
            **{f"wilcoxon_{k}": v for k, v in test.items()},
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
            f"{str(summary['duration_sec']):>8}s  "
            f"wait mean {str(summary['wait_mean']):>7}  "
            f"p90 {str(summary['wait_p90']):>7}  "
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
        for key, block in aggregate["per_contrast"].items():
            p = block["wilcoxon_p_value"]
            print(
                f"  {key}: Δwait mean of plan means "
                f"{block['delta_wait_mean_of_plan_means']} over {block['plans']} plans, "
                f"p={'n/a' if p is None else f'{p:.2e}'}"
            )
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
