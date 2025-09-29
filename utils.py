from config import directionNumbers, speeds
import state

# Example weights (you can tune these)
VEHICLE_WEIGHTS = {
    "car": 1.0,
    "bike": 0.5,
    "truck": 2.0,
    "bus": 2.5
}

def get_weighted_vehicle_counts():
    """
    Returns a dictionary with the weighted count of uncrossed vehicles for each direction.
    Weights depend on vehicle type.
    """
    counts = {}
    for index, direction in directionNumbers.items():
        lanes = state.vehicles[direction]
        weighted_count = 0
        for lane in range(3):
            for vehicle in lanes[lane]:
                if not vehicle.crossed:
                    speed = speeds.get(vehicle.get_type(), 1.0)
                    weight = 1 / speed  # Higher speed -> lower weight
                    weighted_count += weight  # Higher speed -> lower weight
        counts[direction] = weighted_count
    return counts
# def get_vehicle_counts():
#     """
#     Returns a dictionary with the count of uncrossed vehicles for each direction.
#     """
#     return get_weighted_vehicle_counts()

# old function
def get_vehicle_counts():
    """ 
    Returns a dictionary with the count of uncrossed vehicles for each direction. 
    """ 
    counts = {} 
    for index, direction in directionNumbers.items(): 
        lanes = state.vehicles[direction] 
        count = sum( 1 for lane in range(3) for vehicle in lanes[lane] if not vehicle.crossed ) 
        counts[direction] = count 
    return counts