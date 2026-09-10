"""
Green-duration rules and their bounds, in one place.

Both the proposed controller and its duration ablation size a green from the
same demand weight, and the fairness variant uses the same shape with its own
coefficient and ceiling.  The rule used to be written out once per controller,
so a test had to inspect the source of one to prove the other had not drifted.
It lives here instead, and every controller calls it.

Deliberately dependency-light: no pygame, no `state`, no config.  Analyzers
import `GREEN_BOUNDS` to report a green against the ceiling its own controller
actually had, and must not pull the simulator in to do it.
"""

# (per-vehicle seconds, minimum green, maximum green) per controller.
# `None` means the controller does not size greens from demand at all.
DURATION_RULES = {
    'priority': (0.75, 6, 24),
    'fairness_priority': (0.67, 6, 18),
    'fixed_order_adaptive_duration': (0.75, 6, 24),
    'fixed': None,
    'adaptive_order_fixed_duration': None,
}

# Recorded duration bounds per controller, for reports that ask how often a
# controller sat on a bound.  A fixed-duration arm has one value, not a range.
GREEN_BOUNDS = {
    'priority': (6, 24),
    'fairness_priority': (6, 18),
    'fixed_order_adaptive_duration': (6, 24),
    'fixed': None,
    'adaptive_order_fixed_duration': None,
}


def adaptive_green(weight, per_vehicle_sec, minimum, maximum):
    """
    Seconds of green for a demand `weight`, clamped to the controller's bounds.

    Truncating before clamping is deliberate and is the original behaviour:
    the granted green is a whole number of one-second timer ticks.
    """
    return max(minimum, min(int(weight * per_vehicle_sec), maximum))


def green_for(controller, weight, fixed_seconds):
    """
    The green `controller` would grant for `weight`.

    Controllers that do not size greens from demand return `fixed_seconds`,
    which is the configured default for that approach.
    """
    rule = DURATION_RULES.get(controller)
    if rule is None:
        return fixed_seconds
    return adaptive_green(weight, *rule)


def priority_green(weight):
    """The proposed controller's rule."""
    return adaptive_green(weight, *DURATION_RULES['priority'])


def fairness_green(weight):
    """The fairness variant: a smaller coefficient and a lower ceiling."""
    return adaptive_green(weight, *DURATION_RULES['fairness_priority'])
