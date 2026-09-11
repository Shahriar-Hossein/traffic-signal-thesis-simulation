"""Explicit lane snapshots for validating the internal traffic model."""
from core.detectors import in_detection_zone


def capture_lane_observations(direction, elapsed_sec, vehicles_by_lane=None):
    """Capture uncrossed, waiting, and detector-zone counts by incoming lane.

    ``uncrossed_count`` includes vehicles anywhere in the lane, including
    those still off-screen.  These observations describe the model state;
    they are not capacity, saturation, or utilisation measurements.
    """
    if vehicles_by_lane is None:
        import state
        vehicles_by_lane = state.vehicles[direction]

    lanes = []
    for lane in range(3):
        vehicles = list(vehicles_by_lane[lane])
        uncrossed = [vehicle for vehicle in vehicles
                     if not getattr(vehicle, 'crossed', False)]
        lanes.append({
            'lane': lane,
            'uncrossed_count': len(uncrossed),
            'stopped_count': sum(
                1 for vehicle in uncrossed
                if getattr(vehicle, 'is_waiting', False)
            ),
            'detection_zone_count': sum(
                1 for vehicle in uncrossed
                if in_detection_zone(vehicle, direction)
            ),
        })
    return {
        'sample_elapsed_sec': round(float(elapsed_sec), 4),
        'direction': direction,
        'lanes': lanes,
    }
