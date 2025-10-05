# core/generator.py
import state
import random
import time
from models.vehicle import Vehicle
from config import directionNumbers, vehicleTypes

def generateVehicles(uneven_mode=None):
    """
    Generate vehicles continuously with uneven direction probabilities.
    Modes:
        - None or 'uniform': equal probability for all directions
        - 'top_right': more vehicles from top and right
        - 'bottom_left': more vehicles from left and bottom
        - 'one_direction': mostly from right (can be changed)
    """
    cnt = 0
    while state.running:
        cnt += 1
        # Randomly select vehicle type
        vehicle_type_index = random.randint(0, 3)

        # Define direction probabilities based on mode
        if uneven_mode == 'top_right':
            # Assign weights: right & up high, left & down low
            directions = ['right', 'down', 'left', 'up']
            weights = [0.35, 0.15, 0.15, 0.35]  # sums to 1
        elif uneven_mode == 'bottom_left':
            directions = ['right', 'down', 'left', 'up']
            weights = [0.15, 0.35, 0.35, 0.15]
        elif uneven_mode == 'one_direction':
            directions = ['right', 'down', 'left', 'up']
            weights = [0.85, 0.05, 0.05, 0.05]
        else:
            # uniform probability
            directions = ['right', 'down', 'left', 'up']
            weights = [0.25, 0.25, 0.25, 0.25]

        direction = random.choices(directions, weights)[0]
        direction_number = list(directionNumbers.values()).index(direction)

        lane_count = 3
        lane_number = random.randint(0, lane_count - 1)

        Vehicle(
            lane_number,
            vehicleTypes[vehicle_type_index],
            direction_number,
            direction
        )
        time.sleep(1) # 1 second interval between vehicle generations   

        # print(f"Generated vehicle {cnt}: {direction} lane {lane_number}")
        # if cnt % 5 == 0:  # Log every 5th vehicle
        #     time.sleep(1) # Slightly longer pause for high traffic   
