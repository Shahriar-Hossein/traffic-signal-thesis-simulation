"""Priority green rule and the fixed controller declaration."""

# (per-vehicle seconds, minimum green, maximum green) per controller.
# `None` means the controller does not size greens from demand at all.
DURATION_RULES = {
    'priority': (0.75, 6, 24),
    'fixed': None,
}

GREEN_BOUNDS = {
    'priority': (6, 24),
    'fixed': None,
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
