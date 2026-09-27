"""Stop-line presence zone used in phase lane observations."""
from config import stopLines


# The detector is a single, approach-wide presence zone, measured in the
# simulator's pixels.  Keep this module free of pygame/state imports so the
# observation rule is easy to inspect and is captured in source provenance.
DETECTION_ZONE_PX = 100


def vehicle_front(vehicle, direction):
    """Return a vehicle's leading coordinate along its original approach."""
    rect = vehicle.image.get_rect()
    if direction == 'right':
        return vehicle.x + rect.width
    if direction == 'down':
        return vehicle.y + rect.height
    if direction == 'left':
        return vehicle.x
    if direction == 'up':
        return vehicle.y
    raise ValueError(f'unknown approach direction {direction!r}')


def in_detection_zone(vehicle, direction, zone_px=DETECTION_ZONE_PX):
    """Whether one uncrossed vehicle occupies ``direction``'s presence zone."""
    if vehicle.crossed:
        return False

    front = vehicle_front(vehicle, direction)
    stop_line = stopLines[direction]
    if direction in ('right', 'down'):
        return stop_line - zone_px <= front <= stop_line
    return stop_line <= front <= stop_line + zone_px
