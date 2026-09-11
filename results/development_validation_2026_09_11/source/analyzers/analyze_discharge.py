"""
Discharge behaviour of the simulated intersection.

Traffic-model validation, not controller comparison: it joins each crossing to
the green phase that released it and reports the headways between successive
crossings in a lane, together with how much of each green saw traffic move.

    python3 analyzers/analyze_discharge.py data/paired/even_500_seed201/r1

Two things this report deliberately does not claim.

  * These are not saturation-flow and startup-lost-time measurements. Both of
    those are defined against a *standing queue*, and nothing here observes
    queue length at green onset. What is observable from a crossing log is
    named for what it is: the delay to the first crossing (which includes the
    leading vehicle's approach travel when nobody was queued), and crossings
    per second of green on greens that served several vehicles.
  * There is no residual-queue measure. Reporting one would need per-lane
    occupancy at green end, which is not logged.

Headways are measured between successive crossings on the same approach and
lane within one green. Cross-green gaps are excluded: they measure the signal,
not the discharge.
"""
import argparse
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzers.analyze_paired import load_arm, percentile  # noqa: E402
from analyzers.analyze_timing import numeric, phase_records  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Sprite lengths along the direction of travel, measured from images/. They
# are a property of those image files, so a report says whether the files the
# run recorded are still the files these numbers came from.
VEHICLE_LENGTH_PX = {'car': 54, 'bus': 76, 'truck': 62, 'bike': 38}

# A green that served fewer than this cannot say anything about sustained
# discharge. It is a floor on evidence, not a definition of saturation.
MIN_CROSSINGS_FOR_RATE = 3


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


def sprites_unchanged(meta):
    """
    Whether the sprite files this run recorded are still the ones on disk.

    The lengths above were measured from those files. If the images have
    changed since, the geometry the prediction assumes is not the geometry the
    run had, and the prediction is withheld rather than quietly restated.
    """
    recorded = (meta or {}).get('source_files')
    if not isinstance(recorded, dict):
        return None
    images = {name: digest for name, digest in recorded.items()
              if name.startswith('images/')}
    if not images:
        return None
    for name, digest in images.items():
        path = ROOT / name
        if not path.exists():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            return False
    return True


def predicted_headways(meta, fps):
    """
    The headway *this run's* configuration implies, per leading vehicle type.

    Following distance is a fixed number of pixels, so a headway is just
    `(length + movingGap) / (speed * FPS)` — arithmetic, not emergent. Printing
    it beside the measured value turns "the model discharges too fast" into a
    statement about named parameters, and catches the case where the two stop
    agreeing because something other than car-following is limiting flow.

    The gap and speeds come from the configuration the run captured at
    startup, never from the live `config` module: recalibrating the project
    must not change what an archived run is reported to have predicted.
    """
    configuration = (meta or {}).get('configuration')
    if not isinstance(configuration, dict) or not fps:
        return {}, 'no captured configuration'

    gap = configuration.get('movingGap')
    speeds = configuration.get('speeds')
    if not isinstance(gap, (int, float)) or not isinstance(speeds, dict):
        return {}, 'captured configuration has no movingGap/speeds'
    if sprites_unchanged(meta) is False:
        return {}, 'sprite geometry has changed since the run'

    predicted = {}
    for name, speed in speeds.items():
        length = VEHICLE_LENGTH_PX.get(name)
        if length and isinstance(speed, (int, float)) and speed:
            predicted[name] = round((length + gap) / (speed * fps), 3)
    return predicted, None


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
        return {'arm_dir': os.path.abspath(arm_dir), 'error': arm['error']}

    meta = arm.get('meta') or {}
    fps = meta.get('fps_mean')
    phases, unattributed = assign_to_phases(arm)

    # A green the run ended in the middle of served real vehicles, but its
    # duration is not a granted duration. It counts towards what was served
    # and is excluded from everything normalised by green length.
    complete = [phase for phase in phases if phase['status'] != 'censored']
    censored = len(phases) - len(complete)

    served = [len(phase['crossings']) for phase in phases]

    headways = []
    by_leader = {}
    first_crossing_delay = []
    span_fraction = []
    for phase in phases:
        moments = sorted(moment for moment, _, _ in phase['crossings'])
        if moments:
            # Green onset to the first crossing. This is *not* startup lost
            # time: with no queue at onset it is mostly approach travel.
            first_crossing_delay.append(moments[0] - phase['start'])
        if phase['status'] != 'censored' and phase['actual'] > 0:
            # The share of the green between onset and the last crossing.
            # Empty greens count as zero — excluding them would report the
            # utilisation of greens that happened to be used, which is not
            # the utilisation of the signal.
            span_fraction.append(
                min(1.0, (moments[-1] - phase['start']) / phase['actual'])
                if moments else 0.0
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

    rates = [len(phase['crossings']) / phase['actual'] for phase in complete
             if phase['actual'] > 0
             and len(phase['crossings']) >= MIN_CROSSINGS_FOR_RATE]

    served_spans = [value for value in span_fraction if value > 0]
    predicted, prediction_error = predicted_headways(meta, fps)

    return {
        'arm_dir': os.path.abspath(arm_dir),
        'arm': arm['arm'],
        'controller': meta.get('controller'),
        'phases': len(phases),
        # A censored final phase is normal; more than one means the log is
        # not describing the run.
        'phases_censored': censored,
        'phase_log_complete': censored <= 1 and bool(phases),
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
        # Green onset to first crossing, including approach travel. Named for
        # what it measures; it is not startup lost time.
        'first_crossing_delay_mean_sec': (
            round(statistics.fmean(first_crossing_delay), 3)
            if first_crossing_delay else None
        ),
        # Onset to last crossing as a share of the green, over every complete
        # green including the empty ones. This is the span in which discharge
        # happened, not the fraction of green spent discharging.
        'discharge_span_fraction_mean': (
            round(statistics.fmean(span_fraction), 3) if span_fraction else None
        ),
        'discharge_span_fraction_mean_served_greens': (
            round(statistics.fmean(served_spans), 3) if served_spans else None
        ),
        # Crossings per second of green, on greens that served at least
        # MIN_CROSSINGS_FOR_RATE vehicles. A queue was not observed, so this
        # is a throughput rate under unknown demand, not saturation capacity.
        'crossings_per_green_second_mean': (
            round(statistics.fmean(rates), 3) if rates else None
        ),
        'crossings_per_green_second_max': round(max(rates), 3) if rates else None,
        'greens_qualifying_for_rate': len(rates),
        'headway_p05_by_leader': {
            kind: round(percentile(gaps, 0.05), 3)
            for kind, gaps in sorted(by_leader.items()) if gaps
        },
        # What this run's own captured configuration implies the saturated
        # headway should be, under the stated following assumptions.
        'headway_predicted_by_leader': predicted,
        'headway_prediction_withheld': prediction_error,
        'residual_queue_measured': False,
    }


def print_report(report):
    if report.get('error'):
        print(f"⛔ {report['arm_dir']}: {report['error']}")
        return
    print(f"\n=== discharge: {report['arm']} ({report['controller']}) ===")
    print(f"  phases {report['phases']} (censored {report['phases_censored']}), "
          f"crossings {report['crossings_total']}, "
          f"outside green {report['crossings_outside_green']}, "
          f"empty greens {report['greens_serving_nobody']}")
    print(f"  served/green  mean {report['served_per_green_mean']} "
          f"max {report['served_per_green_max']}")
    print(f"  headway (s)   mean {report['headway_mean_sec']} "
          f"median {report['headway_median_sec']} "
          f"p05 {report['headway_p05_sec']} p95 {report['headway_p95_sec']} "
          f"n={report['headways_measured']}")
    print(f"  first crossing after onset {report['first_crossing_delay_mean_sec']}s "
          f"(includes approach travel), discharge span "
          f"{report['discharge_span_fraction_mean']} of green")
    print(f"  crossings/green-second mean {report['crossings_per_green_second_mean']} "
          f"max {report['crossings_per_green_second_max']} "
          f"over {report['greens_qualifying_for_rate']} greens serving "
          f"{MIN_CROSSINGS_FOR_RATE}+ (queue not observed)")
    measured = report['headway_p05_by_leader']
    predicted = report['headway_predicted_by_leader']
    if report['headway_prediction_withheld']:
        print(f"  prediction withheld: {report['headway_prediction_withheld']}")
    elif measured and predicted:
        print("  saturated headway by leading vehicle "
              "(measured p05 vs this run's config):")
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
