# utils.py

from vehicle import vehicles
from config import directionNumbers

def get_vehicle_counts():
    counts = {}
    for i in range(4):  # 0:right, 1:down, 2:left, 3:up
        direction = directionNumbers[i]
        count = sum(1 for lane in range(3) for v in vehicles[direction][lane] if not v.crossed)
        counts[direction] = count
    return counts
