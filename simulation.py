import random
import time
import threading
from typing import List

from config import (
    defaultGreen, defaultRed, defaultYellow,
    directionNumbers, vehicleTypes, defaultStop,
    noOfSignals
)
from vehicle import vehicles, Vehicle
from traffic_signal import TrafficSignal, signals
from utils import get_vehicle_counts

# Global simulation state (can move to config.py if shared)
currentGreen = 0
currentYellow = 0


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
    global currentGreen, currentYellow

    while True:
        # Sort signal priority by current vehicle count
        vehicle_counts_snapshot = get_vehicle_counts()
        signal_queue = sorted(vehicle_counts_snapshot.items(), key=lambda x: x[1], reverse=True)
        signal_order: List[int] = [
            list(directionNumbers.keys())[list(directionNumbers.values()).index(direction)]
            for direction, _ in signal_queue
        ]

        for currentGreen in signal_order:
            vehicle_count = get_vehicle_counts()[directionNumbers[currentGreen]]
            green_time = int(min(vehicle_count * 0.5, 10)) or 2  # Ensure at least 2 seconds

            signals[currentGreen].green = green_time

            # Green phase
            for _ in range(green_time):
                update_signal_timers(currentGreen, yellow=False)
                time.sleep(1)

            # Yellow phase
            currentYellow = 1
            for i in range(3):
                for vehicle in vehicles[directionNumbers[currentGreen]][i]:
                    vehicle.stop = defaultStop[directionNumbers[currentGreen]]
            for _ in range(defaultYellow):
                update_signal_timers(currentGreen, yellow=True)
                time.sleep(1)
            currentYellow = 0

            # Reset this signal's timers
            signals[currentGreen].green = defaultGreen[currentGreen]
            signals[currentGreen].yellow = defaultYellow
            signals[currentGreen].red = defaultRed


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
