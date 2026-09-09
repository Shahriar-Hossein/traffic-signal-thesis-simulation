# core/controllers.py
"""
The set of signal controllers a run may select, in one place.

The dispatch used to fall through to the fixed controller for any unrecognised
name, so a mistyped arm would have run fixed-24 and been reported under the
name it was asked for. Every caller now resolves through this registry and an
unknown name raises.

Imports happen inside `resolve` so that listing the names — which the CLIs and
the analyzers do — costs nothing and cannot import a cycle module in a partly
initialised state.
"""

NAMES = (
    'fixed',
    'priority',
    'fairness_priority',
    # Ablations: each changes exactly one of the two things the proposed
    # controller changes against fixed-24.
    'fixed_order_adaptive_duration',
    'adaptive_order_fixed_duration',
)


def resolve(name):
    """Return the cycle function for `name`, or raise ValueError."""
    if name == 'fixed':
        from core.cycle_fixed import fixed_traffic_cycle
        return fixed_traffic_cycle
    if name == 'priority':
        from core.cycle_priority import control_traffic_cycle
        return control_traffic_cycle
    if name == 'fairness_priority':
        from core.cycle_fairness_priority import fairness_control_traffic_cycle
        return fairness_control_traffic_cycle
    if name == 'fixed_order_adaptive_duration':
        from core.cycle_ablation import fixed_order_adaptive_duration_cycle
        return fixed_order_adaptive_duration_cycle
    if name == 'adaptive_order_fixed_duration':
        from core.cycle_ablation import adaptive_order_fixed_duration_cycle
        return adaptive_order_fixed_duration_cycle
    raise ValueError(f"unknown controller {name!r}; expected one of {list(NAMES)}")
