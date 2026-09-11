"""A bounded fixed-order actuated comparator.

Every approach is offered a green in the normal right/down/left/up rotation.
The phase is eligible to gap out after its six-second minimum only when the
single 100-pixel stop-line presence zone has been empty for two full seconds.
It otherwise runs to the 24-second maximum.  This is a simulator-observable
rule, not a calibration claim about any particular detector installation.
"""
import state

from core.detectors import GapOut, approach_occupied
from core.phase import FIXED_ORDER, all_red_start, decide, run_phase
from core.policy import ACTUATED_GAP_OUT_SEC, ACTUATED_MAX_GREEN, ACTUATED_MIN_GREEN


def actuated_traffic_cycle():
    """Run fixed single-approach phasing with bounded detector gap-out."""
    all_red_start()

    round_index = 0
    while state.running:
        for phase_index, green_index in enumerate(FIXED_ORDER):
            weights, queues, _ = decide(green_index)
            gap_out = GapOut(approach_occupied, ACTUATED_MIN_GREEN,
                             ACTUATED_GAP_OUT_SEC)
            run_phase(green_index, ACTUATED_MAX_GREEN, round_index,
                      phase_index, weights, queues, red_extra=0,
                      early_exit=gap_out)
        round_index += 1
