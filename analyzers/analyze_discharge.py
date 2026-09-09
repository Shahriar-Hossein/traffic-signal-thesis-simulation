"""
Discharge behaviour of the simulated intersection.

Traffic-model validation, not controller comparison: it joins each crossing
to the green phase that released it and reports headways, saturation flow and
startup lost time — the quantities a real intersection is calibrated against.
Green utilisation and residual queues come from the same join.

    python3 analyzers/analyze_discharge.py data/paired/even_500_seed201/r1

Headways are measured between successive crossings on the same approach
within one green. Cross-green gaps are excluded: they measure the signal, not
the discharge.
"""
import argparse
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzers.analyze_paired import load_arm, percentile  # noqa: E402
from analyzers.analyze_timing import numeric, phase_records  # noqa: E402
from config import movingGap, speeds  # noqa: E402

# Sprite lengths along the direction of travel, from images/.
VEHICLE_LENGTH_PX = {'car': 54, 'bus': 76, 'truck': 62, 'bike': 38}


def crossings(arm):
    """(crossed_sec, direction, lane, type) for every crossing, in time order."""
    events = []
    for row in arm['rows']:
        moment = numeric(row, 'crossed_sec')
        if moment is not None and row.get('direction'):
            events.append((moment, row['direction'], row.get('lane'),
                           row.get('vehicle_type')))
    events.sort()
    return events


def predicted_headways(fps):
    """
    Headway the configuration implies, per leading vehicle type.

    Following distance is a fixed number of pixels, so a headway is just
    `(length + movingGap) / (speed * FPS)` — arithmetic, not emergent. Printing
    it beside the measured value turns "the model discharges too fast" into a
    statement about named parameters, and catches the case where the two stop
    agreeing because something other than car-following is limiting flow.
    """
    if not fps:
        return {}
    predicted = {}
    for name, speed in speeds.items():
        length = VEHICLE_LENGTH_PX.get(name)
        if length and speed:
            predicted[name] = round((length + movingGap) / (speed * fps), 3)
    return predicted


def assign_to_phases(arm):
    """
    Group crossings by the green that released them.

    A vehicle is attributed to a phase when it crosses between that phase's
    green onset and its end, on that phase's approach. Crossings that fall in
    no green are counted separately rather than forced into the nearest one:
    they would silently inflate the discharge rate.
    """
    phases = [dict(record, crossings=[]) for record in phase_records(arm)]
    by_direction = {}
    for phase in phases:
        by_direction.setdefault(phase['direction'], []).append(phase)

    unattributed = 0
    for moment, direction, lane, kind in crossings(arm):
        for phase in by_direction.get(direction, ()):
            if phase['start'] <= moment <= phase['start'] + phase['actual']:
                phase['crossings'].append((moment, lane, kind))
                break
        else:
            unattributed += 1
    return phases, unattributed


def analyze_discharge(arm_dir):
    arm = load_arm(arm_dir)
    if arm.get('error'):
        return {'arm_dir': arm_dir, 'error': arm['error']}

    fps = (arm.get('meta') or {}).get('fps_mean')
    phases, unattributed = assign_to_phases(arm)
    served = [len(phase['crossings']) for phase in phases]

    headways = []
    by_leader = {}
    startup = []
    utilisation = []
    for phase in phases:
        moments = [moment for moment, _, _ in phase['crossings']]
        if moments:
            # Time from green onset to the first crossing: startup lost time
            # plus the distance the leading vehicle had to cover.
            startup.append(moments[0] - phase['start'])
            # Fraction of the green that discharged vehicles at all.
            utilisation.append(
                min(1.0, (moments[-1] - phase['start']) / phase['actual'])
                if phase['actual'] > 0 else None
            )
        # Headways are per lane. The three lanes of an approach discharge in
        # parallel, so an approach-wide gap is not a headway at all — it
        # reads as near zero whenever two lanes release together.
        by_lane = {}
        for moment, lane, kind in phase['crossings']:
            by_lane.setdefault(lane, []).append((moment, kind))
        for lane_moments in by_lane.values():
            lane_moments.sort()
            for (earlier, leader), (later, _) in zip(lane_moments, lane_moments[1:]):
                gap = later - earlier
                headways.append(gap)
                # Attributed to the *leader*: it is the vehicle ahead whose
                # length and speed set the gap the follower can close to.
                by_leader.setdefault(leader, []).append(gap)

    utilisation = [value for value in utilisation if value is not None]
    saturating = [len(phase['crossings']) / phase['actual']
                  for phase in phases if phase['actual'] > 0 and len(phase['crossings']) >= 3]

    return {
        'arm_dir': os.path.abspath(arm_dir),
        'arm': arm['arm'],
        'controller': (arm.get('meta') or {}).get('controller'),
        'phases': len(phases),
        'crossings_total': len(arm['rows']),
        # Crossings during no green at all. Yellow-time crossings land here,
        # so a small share is expected; a large one means the join is wrong.
        'crossings_outside_green': unattributed,
        'served_per_green_mean': round(statistics.fmean(served), 2) if served else None,
        'served_per_green_max': max(served) if served else None,
        'greens_serving_nobody': sum(1 for count in served if count == 0),
        'headway_mean_sec': round(statistics.fmean(headways), 3) if headways else None,
        'headway_median_sec': round(statistics.median(headways), 3) if headways else None,
        'headway_p05_sec': round(percentile(headways, 0.05), 3) if headways else None,
        'headway_p95_sec': round(percentile(headways, 0.95), 3) if headways else None,
        'headways_measured': len(headways),
        'startup_delay_mean_sec': round(statistics.fmean(startup), 3) if startup else None,
        'green_utilisation_mean': round(statistics.fmean(utilisation), 3) if utilisation else None,
        # Vehicles per second of green on a green that actually had a queue.
        'discharge_rate_mean_vps': round(statistics.fmean(saturating), 3) if saturating else None,
        'discharge_rate_max_vps': round(max(saturating), 3) if saturating else None,
        'headway_p05_by_leader': {
            kind: round(percentile(gaps, 0.05), 3)
            for kind, gaps in sorted(by_leader.items()) if gaps
        },
        # What the configuration says the saturated headway should be. The
        # measured p05 is the closest thing to a saturated observation.
        'headway_predicted_by_leader': predicted_headways(fps),
    }


def print_report(report):
    if report.get('error'):
        print(f"⛔ {report['arm_dir']}: {report['error']}")
        return
    print(f"\n=== discharge: {report['arm']} ({report['controller']}) ===")
    print(f"  phases {report['phases']}, crossings {report['crossings_total']}, "
          f"outside green {report['crossings_outside_green']}, "
          f"empty greens {report['greens_serving_nobody']}")
    print(f"  served/green  mean {report['served_per_green_mean']} "
          f"max {report['served_per_green_max']}")
    print(f"  headway (s)   mean {report['headway_mean_sec']} "
          f"median {report['headway_median_sec']} "
          f"p05 {report['headway_p05_sec']} p95 {report['headway_p95_sec']} "
          f"n={report['headways_measured']}")
    print(f"  startup delay {report['startup_delay_mean_sec']}s, "
          f"green utilisation {report['green_utilisation_mean']}")
    print(f"  discharge     mean {report['discharge_rate_mean_vps']} veh/s "
          f"max {report['discharge_rate_max_vps']} veh/s")
    measured = report['headway_p05_by_leader']
    predicted = report['headway_predicted_by_leader']
    if measured and predicted:
        print("  saturated headway by leading vehicle (measured p05 vs config):")
        for kind in sorted(set(measured) | set(predicted)):
            print(f"    {kind:6} measured {str(measured.get(kind)):>6}s  "
                  f"predicted {str(predicted.get(kind)):>6}s")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('arm_dir', nargs='+', help='one or more arm folders')
    parser.add_argument('--json', action='store_true', help='emit JSON instead of text')
    args = parser.parse_args(argv)

    reports = [analyze_discharge(directory) for directory in args.arm_dir]
    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        for report in reports:
            print_report(report)


if __name__ == '__main__':
    main()
