# core/cycle_fairness_priority.py
"""
Demand ordering with a lower ceiling and an early exit.

Two differences from the proposed controller: greens are sized with a smaller
coefficient and capped at 18 seconds rather than 24, and a green ends early
once the approach has almost drained.  The order is decided once per round
here and not re-ranked between phases.
"""
import state
from core.phase import (
    FIXED_ORDER, all_red_start, decide, rank_by_demand, run_phase,
)
from core.policy import fairness_green
from utils.counters import get_weighted_vehicle_counts

# Below this many vehicles per lane, and after this many seconds of green, the
# approach has effectively drained and the rest of its green is waste.
DRAINED_PER_LANE = 1
EARLIEST_EXIT_SEC = 6


def _drained(direction, second):
    lane_counts = [len(state.vehicles[direction][lane]) for lane in range(3)]
    if second >= EARLIEST_EXIT_SEC and all(count <= DRAINED_PER_LANE
                                           for count in lane_counts):
        print("EXIT EARLY: Few vehicles remain, ending green phase early.")
        return True
    return False


def fairness_control_traffic_cycle():
    """Serve every approach once per round, in demand order, with a lower cap."""
    all_red_start()

    round_index = 0
    while state.running:
        order = rank_by_demand(list(FIXED_ORDER), get_weighted_vehicle_counts())

        for phase_index, green_index in enumerate(order):
            weights, queues, weight = decide(green_index)
            run_phase(green_index, fairness_green(weight), round_index,
                      phase_index, weights, queues, early_exit=_drained)
        round_index += 1
