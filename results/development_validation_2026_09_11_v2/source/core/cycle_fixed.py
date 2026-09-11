# core/cycle_fixed.py
"""The fixed-time baseline: a fixed rotation with the configured green."""
import state
from config import defaultGreen, directionNumbers
from core.phase import FIXED_ORDER, all_red_start, decide, run_phase


def fixed_traffic_cycle():
    """
    Fixed traffic signal cycle controller.

    Rotates signals in a fixed order (right → down → left → up) with the
    configured green time, regardless of vehicle count.  It sets no extra
    second of red on the served approach, which is the one respect in which
    its timing differs from the demand-sized controllers.
    """
    all_red_start()

    round_index = 0
    while state.running:
        for phase_index, green_index in enumerate(FIXED_ORDER):
            weights, queues, _ = decide(green_index)
            run_phase(green_index, defaultGreen[green_index], round_index,
                      phase_index, weights, queues, red_extra=0)
        round_index += 1
