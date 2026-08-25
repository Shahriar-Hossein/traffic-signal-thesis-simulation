# core/generator.py
import state
import random
import time
from models.vehicle import Vehicle
from config import (
    directionNumbers, vehicleTypes,
    trafficConditions, trafficConditionInterval
)


def pick_traffic_condition(previous=None):
    """
    Randomly pick a traffic condition ('high'/'medium'/'low'),
    always different from the one currently active.
    """
    choices = [c for c in trafficConditions if c != previous]
    return random.choice(choices)


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
    """
    # NOTE: the traffic-condition sequence is unseeded, so two runs of the same
    # length (or the same vehicle quota) see different load sequences.  Seeding
    # is a separate change; see docs/RUN_MODE_VEHICLE_COUNT_PLAN.md.
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

        # Randomly select vehicle type
        vehicle_type_index = random.randint(0, 3)

        # Define direction probabilities based on mode
        # adjacent routes have more vehicles
        if uneven_mode == 'down_left':
            # Assign weights: right & up high, left & down low
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.15,    0.35,   0.35,   0.15]  # sums to 1
        elif uneven_mode == 'right_down':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.35,    0.35,   0.15,   0.15]
        elif uneven_mode == 'right_up':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.35,    0.15,   0.15,   0.35]
        elif uneven_mode == 'left_up':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.15,    0.15,   0.35,   0.35]

        # one direction has more vehicles
        elif uneven_mode == 'up':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.05,    0.05,   0.05,   0.85]
        elif uneven_mode == 'down':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.05,    0.85,   0.05,   0.05]
        elif uneven_mode == 'left':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.05,    0.05,   0.85,   0.05]
        elif uneven_mode == 'right':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.85,    0.05,   0.05,   0.05]

        # alternate routes - up & down, left & right has more vehicles
        elif uneven_mode == 'up_down':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.15,    0.35,   0.15,   0.35]
        elif uneven_mode == 'left_right':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.35,    0.15,   0.35,   0.15]
        
        # uniform probability
        else:
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.25,    0.25,   0.25,   0.25]

        direction = random.choices(directions, weights)[0]
        direction_number = list(directionNumbers.values()).index(direction)

        lane_count = 3
        lane_number = random.randint(0, lane_count - 1)

        Vehicle(
            lane_number,
            vehicleTypes[vehicle_type_index],
            direction_number,
            direction
        )
        state.vehicles_generated += 1
        # print(f"Generated vehicle {cnt}: {direction} lane {lane_number}")

        # Interval between generations, derived from the active condition
        # e.g. 4 vehicles/sec -> 0.25s, 0.5 vehicles/sec -> 2s
        time.sleep(1 / trafficConditions[condition])
