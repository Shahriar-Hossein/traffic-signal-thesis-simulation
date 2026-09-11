# core/controllers.py
"""
The set of signal controllers a run may select, in one place.

The dispatch used to fall through to the fixed controller for any unrecognised
name, so a mistyped arm would have run fixed-24 and been reported under the
name it was asked for. Every caller now resolves through this registry and an
unknown name raises.

The mapping is the single definition: the names come from it rather than being
maintained beside it, so a controller cannot be listed and unresolvable (or
resolvable and unlisted). Modules are imported lazily inside `resolve` so that
listing the names — which the CLIs and the analyzers do — costs nothing and
never drags pygame into an analyzer.
"""
import importlib

# name -> (module, function).  Ablations change exactly one of the two things
# the proposed controller changes against fixed-24.
REGISTRY = {
    'fixed': ('core.cycle_fixed', 'fixed_traffic_cycle'),
    'fixed_tuned': ('core.cycle_tuned_fixed', 'fixed_tuned_traffic_cycle'),
    'priority': ('core.cycle_priority', 'control_traffic_cycle'),
    'fairness_priority': ('core.cycle_fairness_priority',
                          'fairness_control_traffic_cycle'),
    'fixed_order_adaptive_duration': ('core.cycle_ablation',
                                      'fixed_order_adaptive_duration_cycle'),
    'adaptive_order_fixed_duration': ('core.cycle_ablation',
                                      'adaptive_order_fixed_duration_cycle'),
    'actuated': ('core.cycle_actuated', 'actuated_traffic_cycle'),
}

NAMES = tuple(REGISTRY)


def resolve(name):
    """Return the cycle function for `name`, or raise ValueError."""
    try:
        module_name, attribute = REGISTRY[name]
    except (KeyError, TypeError):
        raise ValueError(
            f"unknown controller {name!r}; expected one of {list(NAMES)}"
        ) from None
    return getattr(importlib.import_module(module_name), attribute)
