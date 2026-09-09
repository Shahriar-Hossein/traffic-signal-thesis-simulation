# core/generator.py
import state
import random
import time
from core import runclock
from models.vehicle import Vehicle
from core.plan import (
    sample_vehicle, pick_traffic_condition, DIRECTIONS,
)
from config import (
    trafficConditions, trafficConditionInterval
)

# How long a replay sleep may block before re-checking `state.running`, so a
# window close still stops the thread promptly during a low-rate stretch.
REPLAY_SLEEP_SLICE = 0.05


def generateVehicles(uneven_mode=None):
    """
    Generate vehicles continuously with uneven direction probabilities.
    Modes:
        - None or 'uniform': equal probability for all directions
        - 'top_right': more vehicles from top and right
        - 'bottom_left': more vehicles from left and bottom
        - 'one_direction': mostly from right (can be changed)

    The generation rate switches between the traffic conditions defined in
    config.trafficConditions (high/medium/low) every
    config.trafficConditionInterval seconds, picked at random.

    When state.generation_source == 'plan' this hands off to replay_vehicles,
    which reads a pre-written plan instead of drawing.
    """
    if state.generation_source == 'plan':
        replay_vehicles(state.vehicle_plan)
        return

    # NOTE: the traffic-condition sequence is unseeded, so two runs of the same
    # length (or the same vehicle quota) see different load sequences.  Paired
    # replay runs are the fix for that; see docs/PAIRED_REPLAY_PLAN.md.
    cnt = 0
    condition = None
    condition_started_at = 0  # forces a pick on the first iteration

    while state.running:
        # In 'vehicles' mode the generator releases a fixed quota and stops.
        # The simulation itself keeps running until those vehicles have crossed.
        if (state.run_mode == 'vehicles'
                and state.vehicles_generated >= state.target_vehicle_count):
            print(
                f"Generated all {state.target_vehicle_count} vehicles. "
                "Generator stopping."
            )
            break

        cnt += 1

        # Switch traffic condition every `trafficConditionInterval` seconds
        now = time.time()
        if now - condition_started_at >= trafficConditionInterval:
            condition = pick_traffic_condition(condition)
            condition_started_at = now
            state.traffic_condition = condition
            print(
                f"Traffic condition: {condition} "
                f"({trafficConditions[condition]} vehicles/sec)"
            )

        # Type, direction and lane all come from the shared sampler so the
        # plan writer cannot drift away from what the live mode produces.
        drawn = sample_vehicle(uneven_mode, random)

        Vehicle(
            drawn['lane'],
            drawn['vehicle_type'],
            drawn['direction_number'],
            drawn['direction']
        )
        state.vehicles_generated += 1
        # print(f"Generated vehicle {cnt}: {direction} lane {lane_number}")

        # Interval between generations, derived from the active condition
        # e.g. 4 vehicles/sec -> 0.25s, 0.5 vehicles/sec -> 2s
        time.sleep(1 / trafficConditions[condition])


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
