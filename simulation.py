# simulation.py

import random
import time
import threading
from typing import List

from config import (
    defaultGreen, defaultRed, defaultYellow,
    directionNumbers, vehicleTypes, defaultStop,
    noOfSignals
)
from vehicle import Vehicle
from traffic_signal import TrafficSignal, signals
from utils import get_vehicle_counts
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

    control_traffic_cycle()


def control_traffic_cycle():
    """
    Main traffic signal cycle controller that runs forever.
    Prioritizes lanes based on dynamic vehicle queue.
    """

    while True:
        # Sort signal priority by current vehicle count
        vehicle_counts_snapshot = get_vehicle_counts()
        signal_queue = sorted(vehicle_counts_snapshot.items(), key=lambda x: x[1], reverse=True)
        signal_order: List[int] = [
            list(directionNumbers.keys())[list(directionNumbers.values()).index(direction)]
            for direction, _ in signal_queue
        ]

        for green_index in signal_order:
            state.currentGreen = green_index

            vehicle_count = get_vehicle_counts()[directionNumbers[green_index]]
            green_time = int(min(vehicle_count * 0.5, 10)) or 2

            signals[green_index].green = green_time

            for _ in range(green_time):
                update_signal_timers(green_index, yellow=False)
                time.sleep(1)

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


def generateVehicles():
    """
    Generate vehicles continuously in random directions and lanes.
    """
    while True:
        vehicle_type_index = random.randint(0, 3)
        spawn_chance = random.randint(0, 99)

        # Decide direction based on probability
        thresholds = [25, 50, 75, 100]
        direction_number = next(i for i, t in enumerate(thresholds) if spawn_chance < t)

        lane_count = 3
        lane_number = random.randint(0, lane_count - 1)

        Vehicle(
            lane_number,
            vehicleTypes[vehicle_type_index],
            direction_number,
            directionNumbers[direction_number]
        )

        time.sleep(1)


def start_simulation_threads():
    """
    Starts initialization and vehicle generation in separate threads.
    """
    threading.Thread(target=initialize, name="InitializationThread", daemon=True).start()
    threading.Thread(target=generateVehicles, name="VehicleGeneratorThread", daemon=True).start()
