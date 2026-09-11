"""
Timing acceptance report for a paired-replay folder.

The validity gate answers "is this pair reportable". This answers the prior
question: did the two arms actually run on comparable clocks? It compares
release timing, phase timing and frame rate arm against arm, so a controller
effect cannot be confused with one arm simply running faster.

    python3 analyzers/analyze_timing.py data/paired/even_500_seed07

Repeatability is measured by running the same controller as several arms;
every arm is compared against the first.
"""
import argparse
import json
import math
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzers.analyze_paired import load_arm, arm_sort_key, percentile  # noqa: E402
from core.plan import load_plan  # noqa: E402
from core.policy import GREEN_BOUNDS  # noqa: E402
from analyzers.timing_contract import compare_fps, finite, fps_intervals

# A phase whose green was cut short by shutdown. Its recorded duration is a
# censoring time, not a granted duration.
CENSORED = 'censored'

# Acceptance thresholds. Provisional, and recorded as such in
# docs/EXPERIMENT_PROTOCOL.md: they are the values collection is agreed to
# run under, not measurements, and they were not chosen to make the current
# fixtures pass.
ONSET_DRIFT_TOLERANCE_MS = 1000.0
RELEASE_GAP_TOLERANCE_MS = 500.0
GREEN_OVERRUN_TOLERANCE_MS = 1000.0


def numeric(row, key):
    """A finite number, or None. NaN and infinity are missing values here."""
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def phase_records(arm):
    """
    Phases as numbers, in the order they were served.

    Rows that cannot be parsed are dropped *and counted*: a phase log with
    holes in it is a finding about the run, not a shorter log. Runs archived
    before the log carried a status have no status column; their last phase
    is missing rather than censored, which is why `phase_completeness` reports
    the two cases separately.
    """
    records = []
    for row in arm.get('phases') or []:
        start, end = numeric(row, 'green_start_sec'), numeric(row, 'green_end_sec')
        selected = numeric(row, 'green_selected_sec')
        if None in (start, end, selected) or end < start:
            continue
        status = row.get('status') or None
        records.append({
            'direction': row.get('direction'),
            'round_index': numeric(row, 'round_index'),
            'phase_index': numeric(row, 'phase_index'),
            'start': start,
            'selected': selected,
            'actual': end - start,
            'phase_end': numeric(row, 'phase_end_sec'),
            'status': status,
            'termination': row.get('termination') or None,
        })
    return records


def phase_completeness(arm):
    """
    Whether the phase log accounts for every green the signal log recorded.

    One signal-change row is written per green onset, so the two counts must
    agree. They did not: the controller thread was killed before the final
    phase wrote its record, and the crossings that green served then looked
    like crossings during no green at all.
    """
    rows = arm.get('phases') or []
    records = phase_records(arm)
    onsets = arm.get('signal_changes')
    censored = sum(1 for record in records if record['status'] == CENSORED)
    missing = None
    if isinstance(onsets, int) and onsets:
        missing = onsets - len(records)
    return {
        'phase_rows': len(rows),
        'phase_rows_unusable': len(rows) - len(records),
        'signal_onsets': onsets,
        'phases_missing': missing,
        'phases_censored': censored,
        # A log with no status column predates phase censoring; its final
        # phase is absent rather than marked, and durations derived from it
        # are missing that phase entirely.
        'records_status': (
            'complete' if missing == 0 and not censored else
            'final phase censored' if missing == 0 else
            'phases missing from the log' if missing else 'unknown'
        ),
    }


def release_times(arm):
    times = {}
    for row in arm['rows']:
        try:
            times[int(row['plan_seq'])] = float(row['released_sec'])
        except (KeyError, TypeError, ValueError):
            continue
    return times


def summarize_timing(arm, plan):
    """Per-arm timing behaviour, independent of any other arm."""
    meta = arm.get('meta') if isinstance(arm.get('meta'), dict) else {}
    controller = meta.get('controller')
    phases = phase_records(arm)
    # Overrun is the sleep loop slipping past a granted duration. A green the
    # controller deliberately ended early, and one the run ended in the middle
    # of, are neither of them overruns and are excluded rather than averaged
    # into the same statistic.
    timed = [record for record in phases
             if record['status'] != CENSORED and record['termination'] != 'early_exit']
    overrun = [record['actual'] - record['selected'] for record in timed]
    greens = [record['selected'] for record in phases if record['status'] != CENSORED]
    bounds = GREEN_BOUNDS.get(controller)
    series = meta.get('fps_windows')
    windows = [value for value in series if finite(value)] if isinstance(series, list) else []

    lateness = []
    if plan:
        planned = {record['seq']: record['t_offset_sec'] for record in plan['vehicles']}
        for seq, released in release_times(arm).items():
            if seq in planned:
                lateness.append(released - planned[seq])

    return {
        'arm': arm['arm'],
        'controller': controller,
        'phases': len(phases),
        'phase_completeness': phase_completeness(arm),
        'greens_ended_early': sum(1 for record in phases
                                  if record['termination'] == 'early_exit'),
        # A green that runs longer than it was granted is the sleep loop
        # slipping, not a decision; it belongs in a timing report, not in the
        # controller's results.
        'green_overrun_mean_ms': round(statistics.fmean(overrun) * 1000, 1) if overrun else None,
        'green_overrun_max_ms': round(max(overrun) * 1000, 1) if overrun else None,
        'green_selected_mean': round(statistics.fmean(greens), 2) if greens else None,
        'green_selected_min': min(greens) if greens else None,
        'green_selected_max': max(greens) if greens else None,
        # How often the duration rule sat on a bound: at a bound the
        # controller is no longer responding to demand. The bounds are this
        # controller's own — the fairness variant's ceiling is 18, and
        # reporting it against 24 would never show it at its ceiling. A
        # controller with no duration rule has no bounds to sit on.
        'green_bounds': list(bounds) if bounds else None,
        'green_at_lower_bound': (
            sum(1 for value in greens if value <= bounds[0]) if bounds else None),
        'green_at_upper_bound': (
            sum(1 for value in greens if value >= bounds[1]) if bounds else None),
        # The whole distribution, not just the bounds: a controller whose
        # greens pile up at one value is not adapting, whatever its mean.
        'green_distribution': {
            str(value): count for value, count in sorted(Counter(greens).items())
        },
        'green_p05': round(percentile(greens, 0.05), 2) if greens else None,
        'green_p95': round(percentile(greens, 0.95), 2) if greens else None,
        'release_lateness_mean_ms': round(statistics.fmean(lateness) * 1000, 1) if lateness else None,
        'release_lateness_p99_ms': round(percentile(lateness, 0.99) * 1000, 1) if lateness else None,
        'release_lateness_max_ms': round(max(lateness) * 1000, 1) if lateness else None,
        'fps_mean': meta.get('fps_mean'),
        'fps_min': meta.get('fps_min'),
        'fps_p05': round(percentile(windows, 0.05), 2) if windows else None,
        'fps_windows': len(windows),
        'fps_evidence': fps_intervals(meta),
        'last_crossing_sec': meta.get('last_crossing_sec'),
        'duration_sec': meta.get('duration_sec'),
    }


def compare_timing(baseline, other, plan):
    """
    Arm-against-arm divergence.

    What this can establish depends entirely on whether the two arms ran the
    *same controller*. Two arms of one controller should serve the same phases
    at the same moments, so divergence there is clock behaviour and is
    reportable as such. Two different controllers diverge by design, and so do
    two arms of controllers that share an order but not a duration rule — the
    fixed-order/adaptive-duration ablation shares `fixed`'s order and grants
    different greens, so its onsets drift from `fixed`'s by construction.
    Reporting that as drift would read as a timing fault where there is none.
    """
    base_meta = baseline.get('meta') if isinstance(baseline.get('meta'), dict) else {}
    other_meta = other.get('meta') if isinstance(other.get('meta'), dict) else {}
    same_controller = (base_meta.get('controller') is not None
                       and base_meta.get('controller') == other_meta.get('controller'))

    base_releases, other_releases = release_times(baseline), release_times(other)
    shared = sorted(set(base_releases) & set(other_releases))
    release_gaps = [abs(other_releases[seq] - base_releases[seq]) for seq in shared]

    base_phases, other_phases = phase_records(baseline), phase_records(other)
    aligned = min(len(base_phases), len(other_phases))
    same_direction = sum(1 for i in range(aligned)
                         if other_phases[i]['direction'] == base_phases[i]['direction'])
    # Two sequences can agree over their common prefix and still be different
    # schedules; saying "identical order" of a prefix would overstate it.
    prefix_matches = aligned > 0 and same_direction == aligned
    same_length = len(base_phases) == len(other_phases)
    onset_gaps = ([abs(other_phases[i]['start'] - base_phases[i]['start'])
                   for i in range(aligned)] if prefix_matches else [])
    divergence = round(max(onset_gaps) * 1000, 1) if onset_gaps else None

    fps = compare_fps(base_meta, other_meta)
    window_gaps = fps['gaps']
    windows_aligned = fps['comparable']

    base_clearance = base_meta.get('last_crossing_sec')
    other_clearance = other_meta.get('last_crossing_sec')

    return {
        'baseline': baseline['arm'],
        'arm': other['arm'],
        # Everything below is read differently in these two cases.
        'same_controller': same_controller,
        'matched_vehicles': len(shared),
        'release_gap_mean_ms': round(statistics.fmean(release_gaps) * 1000, 1) if release_gaps else None,
        'release_gap_max_ms': round(max(release_gaps) * 1000, 1) if release_gaps else None,
        'phases_compared': aligned,
        'phase_order_matches_over_prefix': prefix_matches,
        'phase_counts_equal': same_length,
        # Repeatability: the same controller's onsets should not move. None
        # when the arms served different orders — not comparable, not zero.
        'phase_onset_drift_max_ms': divergence if same_controller else None,
        # Descriptive: how far two *different* schedules drift apart. This is
        # a design difference, not a clock fault.
        'phase_onset_divergence_max_ms': None if same_controller else divergence,
        'fps_window_gap_max_pct': round(max(window_gaps) * 100, 2) if window_gaps else None,
        'fps_window_gap_p95_pct': round(percentile(window_gaps, 0.95) * 100, 2) if window_gaps else None,
        'fps_windows_comparable': windows_aligned,
        'fps_common_coverage': fps['common_coverage'],
        # None, not zero: an arm with no recorded clearance has not cleared
        # in the same time as the baseline, it has not reported one.
        'clearance_gap_sec': (
            round(other_clearance - base_clearance, 3)
            if isinstance(base_clearance, (int, float))
            and isinstance(other_clearance, (int, float)) else None
        ),
    }


def acceptance(report, fps_tolerance=0.05):
    """
    Whether this folder's timing evidence supports a comparison.

    Three dispositions, never a silent pass: `accepted`, `rejected` when
    something measured is out of tolerance, and `insufficient evidence` when
    the telemetry needed to decide is missing or not comparable. The last is
    the case that used to be indistinguishable from the first — a pair with
    no phase logs at all produced a clean-looking report.
    """
    reasons = []
    insufficient = []

    if report['errors']:
        insufficient.extend(report['errors'])
    if not report['arms']:
        insufficient.append('no readable arms')

    for arm in report['arms']:
        completeness = arm['phase_completeness']
        if completeness['records_status'] == 'phases missing from the log':
            reasons.append(
                f"{arm['arm']}: {completeness['phases_missing']} of "
                f"{completeness['signal_onsets']} greens are missing from the phase log"
            )
        elif completeness['records_status'] == 'unknown':
            insufficient.append(f"{arm['arm']}: phase log cannot be checked for completeness")
        if completeness['phase_rows_unusable']:
            reasons.append(
                f"{arm['arm']}: {completeness['phase_rows_unusable']} unusable phase rows")
        evidence = arm['fps_evidence']
        reasons.extend(f"{arm['arm']}: {error}" for error in evidence['errors'])
        insufficient.extend(f"{arm['arm']}: {error}" for error in evidence['missing'])
        if (arm['green_overrun_max_ms'] is not None
                and arm['green_overrun_max_ms'] > GREEN_OVERRUN_TOLERANCE_MS):
            reasons.append(f"{arm['arm']}: green duration exceeds timing tolerance")

    for contrast in report['contrasts']:
        gap = contrast['fps_window_gap_max_pct']
        if gap is not None and gap > fps_tolerance * 100:
            reasons.append(f"{contrast['baseline']}→{contrast['arm']}: "
                           f"interval FPS divergence {gap}% exceeds {fps_tolerance * 100:g}%")
        if not contrast['fps_windows_comparable']:
            insufficient.append(
                f"{contrast['baseline']}→{contrast['arm']}: frame-rate series "
                f"are not sample-comparable"
            )
        if (contrast['same_controller']
                and contrast['phase_onset_drift_max_ms'] is not None
                and contrast['phase_onset_drift_max_ms'] > ONSET_DRIFT_TOLERANCE_MS):
            reasons.append(
                f"{contrast['baseline']}→{contrast['arm']}: same controller, "
                f"phase onsets drift up to "
                f"{contrast['phase_onset_drift_max_ms']}ms"
            )
        if (contrast['release_gap_max_ms'] is not None
                and contrast['release_gap_max_ms'] > RELEASE_GAP_TOLERANCE_MS):
            reasons.append(
                f"{contrast['baseline']}→{contrast['arm']}: releases differ by up to "
                f"{contrast['release_gap_max_ms']}ms"
            )

    if reasons:
        return {'result': 'rejected', 'reasons': reasons,
                'insufficient_evidence': insufficient}
    if insufficient:
        return {'result': 'insufficient evidence', 'reasons': [],
                'insufficient_evidence': insufficient}
    return {'result': 'accepted', 'reasons': [], 'insufficient_evidence': []}


def timing_report(arms, plan, plan_id, fps_tolerance=0.05):
    usable = [arm for arm in arms if not arm.get('error')]
    report = {
        'plan_id': plan_id,
        'errors': [f"{arm['arm']}: {arm['error']}" for arm in arms if arm.get('error')],
        'arms': [summarize_timing(arm, plan) for arm in usable],
        'contrasts': [compare_timing(usable[0], arm, plan) for arm in usable[1:]],
        'thresholds': {'fps_tolerance': fps_tolerance,
                       'onset_drift_ms': ONSET_DRIFT_TOLERANCE_MS,
                       'release_gap_ms': RELEASE_GAP_TOLERANCE_MS,
                       'green_overrun_ms': GREEN_OVERRUN_TOLERANCE_MS},
    }
    if plan is None:
        report['errors'].append('plan.json could not be verified')
    report['acceptance'] = acceptance(report, fps_tolerance)
    return report


def analyze_timing(plan_dir, write=True, baseline=None, fps_tolerance=0.05):
    plan_dir = os.path.abspath(plan_dir)
    try:
        plan = load_plan(os.path.join(plan_dir, 'plan.json'))
    except (OSError, ValueError, TypeError, KeyError):
        plan = None
    arms = sorted(
        (load_arm(os.path.join(plan_dir, name)) for name in os.listdir(plan_dir)
         if os.path.isdir(os.path.join(plan_dir, name))), key=arm_sort_key)
    if baseline is not None:
        arms.sort(key=lambda arm: arm['arm'] != baseline)
    report = timing_report(arms, plan, os.path.basename(plan_dir), fps_tolerance)
    if baseline is not None and not any(arm['arm'] == baseline for arm in arms):
        report['errors'].append(f'requested baseline {baseline!r} is missing')
        report['acceptance'] = acceptance(report, fps_tolerance)
    if write:
        path = os.path.join(plan_dir, 'timing.json')
        with open(path, 'w') as handle:
            json.dump(report, handle, indent=2, allow_nan=False)
        report['written_to'] = path
    return report


def show(value, unit=''):
    """None means not measurable here, which is not the same as zero."""
    return 'n/a' if value is None else f"{value}{unit}"


def print_report(report):
    print(f"\n=== timing: {report['plan_id']} ===")
    verdict = report['acceptance']
    marks = {'accepted': '✅', 'rejected': '⛔', 'insufficient evidence': '❔'}
    print(f"  {marks[verdict['result']]} {verdict['result']}")
    for reason in verdict['reasons']:
        print(f"     - {reason}")
    for gap in verdict['insufficient_evidence']:
        print(f"     ? {gap}")
    for error in report['errors']:
        print(f"  ⛔ {error}")
    for arm in report['arms']:
        bounds = arm['green_bounds']
        at_bounds = (f"(low {arm['green_at_lower_bound']}, "
                     f"high {arm['green_at_upper_bound']} of {bounds[0]}/{bounds[1]})"
                     if bounds else "(fixed duration)")
        print(
            f"  {arm['arm']:14} {str(arm['controller']):8} "
            f"phases {arm['phases']:>4} "
            f"[{arm['phase_completeness']['records_status']}]  "
            f"green mean {show(arm['green_selected_mean']):>6} {at_bounds}  "
            f"overrun max {show(arm['green_overrun_max_ms']):>8}ms  "
            f"release late max {show(arm['release_lateness_max_ms']):>8}ms  "
            f"fps {show(arm['fps_mean']):>6}/{show(arm['fps_p05']):>6}"
        )
    for contrast in report['contrasts']:
        kind = ('same controller: drift'
                if contrast['same_controller'] else 'different schedules: divergence')
        onset = (contrast['phase_onset_drift_max_ms'] if contrast['same_controller']
                 else contrast['phase_onset_divergence_max_ms'])
        print(
            f"  {contrast['baseline']} -> {contrast['arm']}: "
            f"release gap max {show(contrast['release_gap_max_ms'], 'ms')}  "
            f"{kind} {show(onset, 'ms')}  "
            f"order matches over prefix {contrast['phase_order_matches_over_prefix']} "
            f"(equal length {contrast['phase_counts_equal']})  "
            f"fps window gap p95 {show(contrast['fps_window_gap_p95_pct'], '%')} "
            f"[comparable {contrast['fps_windows_comparable']}]  "
            f"clearance Δ {show(contrast['clearance_gap_sec'], 's')}"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan_dir', help='a data/paired/{plan_id} folder')
    parser.add_argument('--no-write', action='store_true', help='print without writing timing.json')
    parser.add_argument('--baseline')
    parser.add_argument('--fps-tolerance', type=float, default=0.05)
    args = parser.parse_args(argv)
    report = analyze_timing(args.plan_dir, write=not args.no_write,
                            baseline=args.baseline, fps_tolerance=args.fps_tolerance)
    print_report(report)
    return 0 if report['acceptance']['result'] == 'accepted' else 1


if __name__ == '__main__':
    sys.exit(main())
