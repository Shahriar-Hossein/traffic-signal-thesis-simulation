# core/generator.py
import state
import time
from core import runclock
from models.vehicle import Vehicle
from core.plan import (
    DIRECTIONS,
)
from config import (
    trafficConditions
)

# How long a replay sleep may block before re-checking `state.running`, so a
# window close still stops the thread promptly during a low-rate stretch.
REPLAY_SLEEP_SLICE = 0.05


def generateVehicles():
    """Release the scheduled plan loaded by main.py."""
    replay_vehicles(state.vehicle_plan)


def replay_vehicles(plan):
    """
    Release the vehicles of a pre-written plan instead of drawing new ones.

    Each vehicle is released against an *absolute* deadline
    (`t_offset_sec` on the shared run clock) rather than by sleeping
    the gap between consecutive vehicles.  Cumulative sleeps let the overshoot
    of every `time.sleep` compound over a run; deadline sleeps let a late
    release be absorbed by the next one, so drift self-corrects instead of
    accumulating.

    A release that is already past its deadline goes out immediately and the
    lateness is recorded — never skipped or hurried, because dropping a
    vehicle would break the pairing with the other arm.
    """
    records = plan['vehicles']
    print(
        f"Replaying plan {plan['header']['plan_id']}: "
        f"{len(records)} vehicles"
    )

    drift_sum_ms = 0.0
    drift_max_ms = 0.0

    for record in records:
        if not state.running:
            break

        deadline = record['t_offset_sec']

        # Sleep toward the deadline in slices so a quit is noticed quickly.
        while state.running:
            remaining = deadline - runclock.elapsed()
            if remaining <= 0:
                break
            time.sleep(min(remaining, REPLAY_SLEEP_SLICE))

        if not state.running:
            break

        lateness_ms = (runclock.elapsed() - deadline) * 1000.0
        drift_sum_ms += lateness_ms
        drift_max_ms = max(drift_max_ms, lateness_ms)

        if record['condition'] != state.traffic_condition:
            state.traffic_condition = record['condition']
            print(
                f"Traffic condition: {record['condition']} "
                f"({trafficConditions[record['condition']]} vehicles/sec)"
            )

        Vehicle(
            record['lane'],
            record['vehicle_type'],
            DIRECTIONS.index(record['direction']),
            record['direction'],
            will_turn=record['will_turn'],
            turn_direction=record['turn_direction'],
            target_turn_lane=record['target_turn_lane'],
            plan_seq=record['seq'],
        )

        state.vehicles_generated += 1
        state.release_count += 1
        state.release_drift_sum_ms = drift_sum_ms
        state.release_drift_max_ms = drift_max_ms

    if state.vehicles_generated >= len(records):
        print(f"Released all {len(records)} planned vehicles. Generator stopping.")
