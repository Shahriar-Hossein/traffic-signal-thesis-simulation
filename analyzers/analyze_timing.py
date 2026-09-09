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
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzers.analyze_paired import load_arm, arm_sort_key, percentile  # noqa: E402
from core.plan import load_plan  # noqa: E402


def numeric(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def phase_records(arm):
    """Phases as numbers, in the order they were served."""
    records = []
    for row in arm.get('phases') or []:
        start, end = numeric(row, 'green_start_sec'), numeric(row, 'green_end_sec')
        selected = numeric(row, 'green_selected_sec')
        if None in (start, end, selected):
            continue
        records.append({
            'direction': row.get('direction'),
            'round_index': numeric(row, 'round_index'),
            'phase_index': numeric(row, 'phase_index'),
            'start': start,
            'selected': selected,
            'actual': end - start,
            'phase_end': numeric(row, 'phase_end_sec'),
        })
    return records


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
    meta = arm.get('meta') or {}
    phases = phase_records(arm)
    overrun = [record['actual'] - record['selected'] for record in phases]
    greens = [record['selected'] for record in phases]
    windows = [value for value in (meta.get('fps_windows') or [])
               if isinstance(value, (int, float))]

    lateness = []
    if plan:
        planned = {record['seq']: record['t_offset_sec'] for record in plan['vehicles']}
        for seq, released in release_times(arm).items():
            if seq in planned:
                lateness.append(released - planned[seq])

    return {
        'arm': arm['arm'],
        'controller': meta.get('controller'),
        'phases': len(phases),
        # A green that runs longer than it was granted is the sleep loop
        # slipping, not a decision; it belongs in a timing report, not in the
        # controller's results.
        'green_overrun_mean_ms': round(statistics.fmean(overrun) * 1000, 1) if overrun else None,
        'green_overrun_max_ms': round(max(overrun) * 1000, 1) if overrun else None,
        'green_selected_mean': round(statistics.fmean(greens), 2) if greens else None,
        'green_selected_min': min(greens) if greens else None,
        'green_selected_max': max(greens) if greens else None,
        # How often the duration rule sat on a bound: at a bound the
        # controller is no longer responding to demand.
        'green_at_lower_bound': sum(1 for value in greens if value <= 6),
        'green_at_upper_bound': sum(1 for value in greens if value >= 24),
        # The whole distribution, not just the bounds: a controller whose
        # greens pile up at one value is not adapting, whatever its mean.
        'green_distribution': {
            str(value): greens.count(value) for value in sorted(set(greens))
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
        'last_crossing_sec': meta.get('last_crossing_sec'),
        'duration_sec': meta.get('duration_sec'),
    }


def compare_timing(baseline, other, plan):
    """Arm-against-arm divergence: the part that invalidates a comparison."""
    base_releases, other_releases = release_times(baseline), release_times(other)
    shared = sorted(set(base_releases) & set(other_releases))
    release_gaps = [abs(other_releases[seq] - base_releases[seq]) for seq in shared]

    base_phases, other_phases = phase_records(baseline), phase_records(other)
    aligned = min(len(base_phases), len(other_phases))
    same_direction = sum(1 for i in range(aligned)
                         if other_phases[i]['direction'] == base_phases[i]['direction'])
    # Phase k against phase k only means something when both arms served the
    # same order. Two different controllers diverge by design, and reporting
    # that divergence as clock drift would read as a timing fault.
    identical_order = aligned > 0 and same_direction == aligned
    onset_gaps = ([abs(other_phases[i]['start'] - base_phases[i]['start'])
                   for i in range(aligned)] if identical_order else [])

    base_windows = (baseline.get('meta') or {}).get('fps_windows') or []
    other_windows = (other.get('meta') or {}).get('fps_windows') or []
    common = min(len(base_windows), len(other_windows))
    window_gaps = [abs(other_windows[i] - base_windows[i]) / max(base_windows[i], 1e-9)
                   for i in range(common)]

    return {
        'baseline': baseline['arm'],
        'arm': other['arm'],
        'matched_vehicles': len(shared),
        'release_gap_mean_ms': round(statistics.fmean(release_gaps) * 1000, 1) if release_gaps else None,
        'release_gap_max_ms': round(max(release_gaps) * 1000, 1) if release_gaps else None,
        'phases_compared': aligned,
        'phase_order_identical': identical_order,
        # None when the arms served different orders: not comparable, not zero.
        'phase_onset_gap_max_ms': round(max(onset_gaps) * 1000, 1) if onset_gaps else None,
        'fps_window_gap_max_pct': round(max(window_gaps) * 100, 2) if window_gaps else None,
        'fps_window_gap_p95_pct': round(percentile(window_gaps, 0.95) * 100, 2) if window_gaps else None,
        'clearance_gap_sec': round(
            (other['meta'].get('last_crossing_sec') or 0)
            - (baseline['meta'].get('last_crossing_sec') or 0), 3),
    }


def analyze_timing(plan_dir, write=True):
    plan_dir = os.path.abspath(plan_dir)
    try:
        plan = load_plan(os.path.join(plan_dir, 'plan.json'))
    except (OSError, ValueError) as error:
        plan = None
        print(f"warning: {error}")

    arms = sorted(
        (load_arm(os.path.join(plan_dir, name)) for name in os.listdir(plan_dir)
         if os.path.isdir(os.path.join(plan_dir, name))),
        key=arm_sort_key,
    )
    usable = [arm for arm in arms if not arm.get('error')]

    report = {
        'plan_id': os.path.basename(plan_dir),
        'errors': [f"{arm['arm']}: {arm['error']}" for arm in arms if arm.get('error')],
        'arms': [summarize_timing(arm, plan) for arm in usable],
        'contrasts': [compare_timing(usable[0], arm, plan) for arm in usable[1:]],
    }

    if write:
        path = os.path.join(plan_dir, 'timing.json')
        with open(path, 'w') as handle:
            json.dump(report, handle, indent=2)
        report['written_to'] = path
    return report


def show(value, unit=''):
    """None means not measurable here, which is not the same as zero."""
    return 'n/a' if value is None else f"{value}{unit}"


def print_report(report):
    print(f"\n=== timing: {report['plan_id']} ===")
    for error in report['errors']:
        print(f"  ⛔ {error}")
    for arm in report['arms']:
        print(
            f"  {arm['arm']:14} {str(arm['controller']):8} "
            f"phases {arm['phases']:>4}  "
            f"green mean {show(arm['green_selected_mean']):>6} "
            f"(low {arm['green_at_lower_bound']}, high {arm['green_at_upper_bound']})  "
            f"overrun max {show(arm['green_overrun_max_ms']):>8}ms  "
            f"release late max {show(arm['release_lateness_max_ms']):>8}ms  "
            f"fps {show(arm['fps_mean']):>6}/{show(arm['fps_p05']):>6}"
        )
    for contrast in report['contrasts']:
        print(
            f"  {contrast['baseline']} -> {contrast['arm']}: "
            f"release gap max {show(contrast['release_gap_max_ms'], 'ms')}  "
            f"phase onset gap max {show(contrast['phase_onset_gap_max_ms'], 'ms')}  "
            f"order identical {contrast['phase_order_identical']}  "
            f"fps window gap p95 {show(contrast['fps_window_gap_p95_pct'], '%')}  "
            f"clearance Δ {contrast['clearance_gap_sec']}s"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan_dir', help='a data/paired/{plan_id} folder')
    parser.add_argument('--no-write', action='store_true', help='print without writing timing.json')
    args = parser.parse_args(argv)
    print_report(analyze_timing(args.plan_dir, write=not args.no_write))


if __name__ == '__main__':
    main()
