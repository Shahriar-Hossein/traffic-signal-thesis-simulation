# core/cycle_ablation.py
"""
Ablation controllers that split the proposed rule into its two parts.

Against fixed-24 the proposed controller changes two things at once: which
approach is served next, and how long its green lasts. Each arm here changes
exactly one of them, so an observed effect can be attributed to ordering or to
duration rather than to their combination.

    fixed_order_adaptive_duration  fixed rotation, demand-sized green
    adaptive_order_fixed_duration  demand-ordered rotation, 24-second green

The duration rule is not restated here: both these arms and the proposed
controller call `core.policy`, so there is one rule and nothing to drift.
"""
import state
from config import defaultGreen
from core.phase import (
    FIXED_ORDER, all_red_start, decide, rank_by_demand, run_phase,
)
from core.policy import priority_green
from utils.counters import get_weighted_vehicle_counts


def fixed_order_adaptive_duration_cycle():
    """Fixed rotation; green sized by the proposed duration rule."""
    all_red_start()

    round_index = 0
    while state.running:
        for phase_index, green_index in enumerate(FIXED_ORDER):
            weights, queues, weight = decide(green_index)
            run_phase(green_index, priority_green(weight), round_index,
                      phase_index, weights, queues)
        round_index += 1


def adaptive_order_fixed_duration_cycle():
    """
    Demand-ordered rotation; every green is the fixed baseline's 24 seconds.

    The ordering logic mirrors the proposed controller: rank the four
    approaches, serve the largest, then recount and reorder only those still
    unserved this round.
    """
    all_red_start()

    round_index = 0
    while state.running:
        order = rank_by_demand(list(FIXED_ORDER), get_weighted_vehicle_counts())

        phase_index = 0
        while order:
            green_index = order.pop(0)
            weights, queues, _ = decide(green_index)
            run_phase(green_index, defaultGreen[green_index], round_index,
                      phase_index, weights, queues)
            phase_index += 1

            if order:
                order = rank_by_demand(order, get_weighted_vehicle_counts())
        round_index += 1
