# simulation.py

import random
import time
import threading
from typing import List
from logger import init_logger
from logger import log_signal_change

from config import (
    defaultGreen, defaultRed, defaultYellow,
    directionNumbers, vehicleTypes, defaultStop,
    noOfSignals
)
from vehicle import Vehicle
from traffic_signal import TrafficSignal, signals
from utils import get_vehicle_counts, get_weighted_vehicle_counts
import state

def initialize():
    """
    Initialize the traffic signals with default values.
    """
    signals.clear()
    ts1 = TrafficSignal(0, defaultYellow, defaultGreen[0])
    ts2 = TrafficSignal(ts1.red + ts1.yellow + ts1.green, defaultYellow, defaultGreen[1])
    ts3 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[2])
    ts4 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[3])

    signals.extend([ts1, ts2, ts3, ts4])

    print(f"[DEBUG] state.currentMode = '{state.currentMode}'")
    if state.currentMode == "priority":
        control_traffic_cycle()
    else:
        fixed_traffic_cycle()


def fixed_traffic_cycle():
    """
    Fixed traffic signal cycle controller.
    Rotates signals in a fixed order (right → down → left → up) 
    with fixed green time, regardless of vehicle count.
    """
    fixed_order = [0, 1, 2, 3]  # right, down, left, up

    # Initially keep all signals red for 10 seconds
    for signal in signals:
        signal.red = 10  # or set to 10 seconds if you want fixed red
        signal.green = 0
        signal.yellow = 0

    state.currentGreen = -1  # No green yet
    state.currentYellow = 0

    print("Initial all-red phase for 10 seconds to accumulate vehicles.")
    for _ in range(10):
        # Just update timers for red signals (they remain red)
        for i in range(noOfSignals):
            signals[i].red = max(0, signals[i].red - 1)
        time.sleep(1)


    while state.running:
        for green_index in fixed_order:
            state.currentGreen = green_index
            log_signal_change(directionNumbers[green_index])

            green_time = defaultGreen[green_index]
            signals[green_index].green = green_time
            signals[green_index].yellow = defaultYellow
            signals[green_index].red = green_time + defaultYellow

            # Green phase
            for _ in range(green_time):
                update_signal_timers(green_index, yellow=False)
                time.sleep(1)

            # Yellow phase
            state.currentYellow = 1
            for i in range(3):
                for vehicle in state.vehicles[directionNumbers[green_index]][i]:
                    vehicle.stop = defaultStop[directionNumbers[green_index]]
            for _ in range(defaultYellow):
                update_signal_timers(green_index, yellow=True)
                time.sleep(1)
            state.currentYellow = 0

            # Reset signal timers
            signals[green_index].green = defaultGreen[green_index]
            signals[green_index].yellow = defaultYellow
            signals[green_index].red = defaultRed


def control_traffic_cycle():
    """
    Main traffic signal cycle controller that runs forever.
    Prioritizes lanes based on dynamic vehicle queue.
    """

    # Initially keep all signals red for 10 seconds
    for signal in signals:
        signal.red = 10  # or set to 10 seconds if you want fixed red
        signal.green = 0
        signal.yellow = 0

    state.currentGreen = -1  # No green yet
    state.currentYellow = 0

    print("Initial all-red phase for 10 seconds to accumulate vehicles.")
    for _ in range(10):
        # Just update timers for red signals (they remain red)
        for i in range(noOfSignals):
            signals[i].red = max(0, signals[i].red - 1)
        time.sleep(1)

    while state.running:
        # Sort signal priority by current vehicle count
        vehicle_counts_snapshot = get_weighted_vehicle_counts()
        signal_queue = sorted(vehicle_counts_snapshot.items(), key=lambda x: x[1], reverse=True)
        signal_order: List[int] = [
            list(directionNumbers.keys())[list(directionNumbers.values()).index(direction)]
            for direction, _ in signal_queue
        ]

        # Cycle through chosen order
        for green_index in signal_order:
            state.currentGreen = green_index
            log_signal_change(directionNumbers[green_index])

            vehicle_count = get_weighted_vehicle_counts()[directionNumbers[green_index]]
            lanes = 3
            avg_headway = 2.0   # seconds per car per lane
            startup_loss = 1    # seconds lost when signal turns green

            # vehicle_required_time = (vehicle_count / lanes) * avg_headway + startup_loss
            vehicle_required_time = vehicle_count * 0.67
            green_time = max(6, min( int( vehicle_required_time ), 18 ) )

            # yellow_time = int(min(vehicle_count * 0.3 + 4, 6))

            signals[green_index].green = green_time
            signals[green_index].yellow = defaultYellow  # keep yellow fixed for simplicity
            signals[green_index].red = green_time + defaultYellow + 1
            for t in range(green_time):
                vc = get_vehicle_counts()[directionNumbers[green_index]]
                if vc <= lanes and t >= 6:
                    # Break early if few vehicles remain after minimum green time
                    break
                update_signal_timers(green_index, yellow=False)
                time.sleep(1)

            state.currentYellow = 1
            for i in range(3):
                for vehicle in state.vehicles[directionNumbers[green_index]][i]:
                    vehicle.stop = defaultStop[directionNumbers[green_index]]
            
            # use yellow_time for dynamic yellow, defaultYellow for fixed
            for _ in range(defaultYellow):
                update_signal_timers(green_index, yellow=True)
                time.sleep(1)
            state.currentYellow = 0

            # Reset signal timers
            signals[green_index].green = defaultGreen[green_index]
            signals[green_index].yellow = defaultYellow
            signals[green_index].red = defaultRed


def update_signal_timers(current_green: int, yellow: bool):
    """
    Update signal countdowns each second.
    """
    for i in range(noOfSignals):
        if i == current_green:
            if yellow:
                signals[i].yellow -= 1
            else:
                signals[i].green -= 1
        else:
            signals[i].red = max(0, signals[i].red - 1)


# def generateVehicles():
#     """
#     Generate vehicles continuously in random directions and lanes.
#     """
#     while state.running:
#         vehicle_type_index = random.randint(0, 3)
#         spawn_chance = random.randint(0, 99)

#         # Decide direction based on probability
#         thresholds = [25, 50, 75, 100]
#         direction_number = next(i for i, t in enumerate(thresholds) if spawn_chance < t)

#         lane_count = 3
#         lane_number = random.randint(0, lane_count - 1)

#         Vehicle(
#             lane_number,
#             vehicleTypes[vehicle_type_index],
#             direction_number,
#             directionNumbers[direction_number]
#         )

#         time.sleep(3)


def generateVehicles(uneven_mode=None):
    """
    Generate vehicles continuously with uneven direction probabilities.
    Modes:
        - None or 'uniform': equal probability for all directions
        - 'top_right': more vehicles from top and right
        - 'bottom_left': more vehicles from left and bottom
        - 'one_direction': mostly from right (can be changed)
    """

    while state.running:
        vehicle_type_index = random.randint(0, 3)

        # Define direction probabilities based on mode
        if uneven_mode == 'top_right':
            # Assign weights: right & up high, left & down low
            directions = ['right', 'down', 'left', 'up']
            weights = [0.35, 0.15, 0.15, 0.35]  # sums to 1
        elif uneven_mode == 'bottom_left':
            directions = ['right', 'down', 'left', 'up']
            weights = [0.15, 0.35, 0.35, 0.15]
        elif uneven_mode == 'one_direction':
            directions = ['right', 'down', 'left', 'up']
            weights = [0.85, 0.05, 0.05, 0.05]
        else:
            # uniform probability
            directions = ['right', 'down', 'left', 'up']
            weights = [0.25, 0.25, 0.25, 0.25]

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

        time.sleep(1) 


def start_simulation_threads():
    """
    Starts initialization and vehicle generation in separate threads.
    """
    init_logger(state.duration, state.uneven_mode)
    threading.Thread(target=initialize, name="InitializationThread", daemon=True).start()
    threading.Thread(target=generateVehicles, name="VehicleGeneratorThread", kwargs={'uneven_mode': state.uneven_mode}, daemon=True).start()
