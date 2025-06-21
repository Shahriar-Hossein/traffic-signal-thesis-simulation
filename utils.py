from config import directionNumbers
import state

def get_vehicle_counts():
    """
    Returns a dictionary with the count of uncrossed vehicles for each direction.
    """
    counts = {}
    for index, direction in directionNumbers.items():
        lanes = state.vehicles[direction]
        count = sum(
            1 for lane in range(3)
            for vehicle in lanes[lane]
            if not vehicle.crossed
        )
        counts[direction] = count
    return counts
