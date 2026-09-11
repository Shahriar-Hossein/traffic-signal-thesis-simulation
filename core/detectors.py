"""Stop-line detector geometry for the simple actuated comparator.

This is an observable simulator definition, not a calibrated field detector.
Each approach has one presence zone extending ``DETECTION_ZONE_PX`` pixels
upstream from its stop line.  A vehicle occupies it when its leading edge is
inside that interval.  Vehicles that have already crossed are excluded even
if they have not yet left the display.
"""
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


def approach_occupied(direction, vehicles=None, zone_px=DETECTION_ZONE_PX):
    """Whether any vehicle in an approach's three incoming lanes is detected."""
    if vehicles is None:
        # Keep the runtime dependency local: offline inspection of the sensor
        # geometry should not initialise simulator state or pygame.
        import state
        vehicles = (
            vehicle for lane in range(3)
            for vehicle in state.vehicles[direction][lane]
        )
    return any(in_detection_zone(vehicle, direction, zone_px) for vehicle in vehicles)


class GapOut:
    """Per-phase gap timer evaluated by ``run_phase`` once before each tick.

    The callback sees the start of second ``second``.  It ends green only once
    the detector has been continuously empty for the requested number of
    *elapsed* one-second intervals; a first empty reading at second 6 cannot
    end a phase until second 8 when the gap is two seconds.
    """

    def __init__(self, occupied, minimum_green, gap_out_seconds):
        self.occupied = occupied
        self.minimum_green = minimum_green
        self.gap_out_seconds = gap_out_seconds
        self.empty_since = None

    def __call__(self, direction, second):
        if self.occupied(direction):
            self.empty_since = None
            return False

        if self.empty_since is None:
            self.empty_since = second
        return (second >= self.minimum_green
                and second - self.empty_since >= self.gap_out_seconds)
