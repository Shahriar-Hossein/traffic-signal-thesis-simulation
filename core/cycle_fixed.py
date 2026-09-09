# core/cycle_fixed.py
from models.traffic_signal import signals
import state
import time
from config import (
    defaultRed, defaultYellow, defaultGreen,
    directionNumbers, noOfSignals, defaultStop
)
from utils.logger import log_signal_change, log_phase
from utils.counters import get_vehicle_counts, get_weighted_vehicle_counts
from core import runclock
from core.updater import update_signal_timers

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


    round_index = 0
    while state.running:
        for phase_index, green_index in enumerate(fixed_order):
            state.currentGreen = green_index
            direction = directionNumbers[green_index]
            log_signal_change(direction)

            weights = get_weighted_vehicle_counts()
            queues = get_vehicle_counts()
            green_start = runclock.elapsed()
            green_time = defaultGreen[green_index]
            signals[green_index].green = green_time
            signals[green_index].yellow = defaultYellow
            signals[green_index].red = green_time + defaultYellow

            # Green phase
            for _ in range(green_time):
                update_signal_timers(green_index, yellow=False)
                time.sleep(1)

            green_end = runclock.elapsed()

            # Yellow phase
            state.currentYellow = 1
            for i in range(3):
                for vehicle in state.vehicles[directionNumbers[green_index]][i]:
                    vehicle.stop = defaultStop[directionNumbers[green_index]]
            for _ in range(defaultYellow):
                update_signal_timers(green_index, yellow=True)
                time.sleep(1)
            state.currentYellow = 0

            log_phase(
                round_index=round_index, phase_index=phase_index,
                direction=direction, green_start_sec=green_start,
                green_selected_sec=green_time, green_end_sec=green_end,
                phase_end_sec=runclock.elapsed(),
                decision_weight=weights[direction],
                decision_counts=weights, queue_counts=queues,
            )

            # Reset signal timers
            signals[green_index].green = defaultGreen[green_index]
            signals[green_index].yellow = defaultYellow
            signals[green_index].red = defaultRed
        round_index += 1
