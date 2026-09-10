# core/cycle_priority.py
"""The proposed controller: demand ordering and demand-sized greens."""
import state
from core.phase import (
    FIXED_ORDER, all_red_start, decide, rank_by_demand, run_phase,
)
from core.policy import priority_green
from utils.counters import get_weighted_vehicle_counts
from config import directionNumbers


def control_traffic_cycle():
    """
    Main traffic signal cycle controller that runs until the run ends.

    Each round it ranks the four approaches by weighted queue, serves the
    largest, and then re-ranks only the approaches still unserved this round —
    so every approach is served exactly once per round, in demand order.  The
    green each one gets is sized from the same snapshot the choice was made
    from (`core.policy.priority_green`).
    """
    all_red_start()

    round_index = 0
    while state.running:
        order = rank_by_demand(list(FIXED_ORDER), get_weighted_vehicle_counts())
        print(f"evaluated signal order: {[directionNumbers[idx] for idx in order]}")

        phase_index = 0
        while order:
            green_index = order.pop(0)
            weights, queues, weight = decide(green_index)
            run_phase(green_index, priority_green(weight), round_index,
                      phase_index, weights, queues)
            phase_index += 1

            if order:
                order = rank_by_demand(order, get_weighted_vehicle_counts())
                print(f"Re-evaluated signal order: "
                      f"{[directionNumbers[idx] for idx in order]}")
        round_index += 1
