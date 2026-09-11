"""Fixed-order controller using an explicitly selected timing table."""
import state

from core.fixed_timing import resolve_fixed_greens
from core.phase import FIXED_ORDER, all_red_start, decide, run_phase


def fixed_tuned_traffic_cycle():
    """Run the fixed order with the plan-selected per-approach greens."""
    all_red_start()
    greens = resolve_fixed_greens(
        state.fixed_timing_plan, state.vehicle_plan['header'])

    round_index = 0
    while state.running:
        for phase_index, green_index in enumerate(FIXED_ORDER):
            weights, queues, _ = decide(green_index)
            run_phase(green_index, greens[green_index], round_index,
                      phase_index, weights, queues, red_extra=0)
        round_index += 1
