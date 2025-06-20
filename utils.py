from vehicle import vehicles
from config import directionNumbers

# Helper function to count uncrossed vehicles for each direction
# def get_vehicle_counts():
#     counts = {}
#     for dir_name in directionNumbers.values():
#         count = 0
#         for lane in range(3):
#             count += sum(1 for vehicle in vehicles[dir_name][lane] if vehicle.crossed == 0)
#         counts[dir_name] = count
#     return counts

def get_vehicle_counts():
    counts = {}
    for i in range(4):  # 0:right, 1:down, 2:left, 3:up
        direction = directionNumbers[i]
        count = sum(1 for lane in range(3) for v in vehicles[direction][lane] if not v.crossed)
        counts[direction] = count
    return counts
