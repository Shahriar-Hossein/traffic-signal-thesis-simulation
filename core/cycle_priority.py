# core/cycle_priority.py
from models.traffic_signal import signals
import state
import time
from config import (
    defaultRed, defaultYellow, defaultGreen,
    directionNumbers, noOfSignals, defaultStop
)
from typing import List, Dict
from utils.counters import get_weighted_vehicle_counts
from utils.logger import log_signal_change, log_phase
from core import runclock
from utils.counters import get_vehicle_counts
from core.updater import update_signal_timers


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

    round_index = 0
    while state.running:
        # Sort signal priority by current vehicle count
        vehicle_counts_snapshot = get_weighted_vehicle_counts()
        signal_queue = sorted(vehicle_counts_snapshot.items(), key=lambda x: x[1], reverse=True)
        signal_order: List[int] = [
            list(directionNumbers.keys())[list(directionNumbers.values()).index(direction)]
            for direction, _ in signal_queue
        ]
        print(f"evaluated signal order: {[directionNumbers[idx] for idx in signal_order]}")
        # Cycle through chosen order
        phase_index = 0
        while signal_order:
            green_index = signal_order.pop(0)
            state.currentGreen = green_index
            direction = directionNumbers[green_index]
            log_signal_change(direction)

            weights = get_weighted_vehicle_counts()
            queues = get_vehicle_counts()
            green_start = runclock.elapsed()
            vehicle_count = weights[direction]
            lanes = 3
            avg_headway = 2.0   # seconds per car per lane
            startup_loss = 1    # seconds lost when signal turns green

            # vehicle_required_time = (vehicle_count / lanes) * avg_headway + startup_loss
            vehicle_required_time = vehicle_count * 0.75
            green_time = max(6, min( int( vehicle_required_time ), 24 ) )

            signals[green_index].green = green_time
            signals[green_index].yellow = defaultYellow  # keep yellow fixed for simplicity
            signals[green_index].red = green_time + defaultYellow + 1
            for t in range(green_time):
                update_signal_timers(green_index, yellow=False)
                time.sleep(1)

            green_end = runclock.elapsed()

            state.currentYellow = 1
            for i in range(3):
                for vehicle in state.vehicles[directionNumbers[green_index]][i]:
                    vehicle.stop = defaultStop[directionNumbers[green_index]]
            
            # use yellow_time for dynamic yellow, defaultYellow for fixed
            for _ in range(defaultYellow):
                update_signal_timers(green_index, yellow=True)
                time.sleep(1)
            state.currentYellow = 0

            log_phase(
                round_index=round_index, phase_index=phase_index,
                direction=direction, green_start_sec=green_start,
                green_selected_sec=green_time, green_end_sec=green_end,
                phase_end_sec=runclock.elapsed(),
                decision_weight=vehicle_count,
                decision_counts=weights, queue_counts=queues,
            )
            phase_index += 1

            # Reset signal timers
            signals[green_index].green = defaultGreen[green_index]
            signals[green_index].yellow = defaultYellow
            signals[green_index].red = defaultRed

            # Re-evaluate priorities for the remaining signals
            if signal_order:
                vehicle_counts_snapshot = get_weighted_vehicle_counts()
                
                #sort remaining signals by updated vehicle counts
                signal_order = sorted(
                    signal_order,
                    key=lambda idx: vehicle_counts_snapshot[directionNumbers[idx]],
                    reverse=True
                )
                print(f"Re-evaluated signal order: {[directionNumbers[idx] for idx in signal_order]}")
                
        round_index += 1
