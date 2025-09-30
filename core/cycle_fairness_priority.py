# core/cycle_fairness_priority.py
from models.traffic_signal import signals
import state
import time
from utils.counters import get_vehicle_counts, get_weighted_vehicle_counts
from config import (
    defaultRed, defaultYellow, defaultGreen,
    directionNumbers, noOfSignals, defaultStop
)
from typing import List, Dict
from utils.logger import log_signal_change
from core.updater import update_signal_timers

def fairness_control_traffic_cycle():
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
                lane_vehicle_counts = [len(state.vehicles[directionNumbers[green_index]][i]) for i in range(3)]
                if all(count <= 1 for count in lane_vehicle_counts) and t >= 6:
                    print("EXIT EARLY: Few vehicles remain, ending green phase early.")
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
