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
        # adjacent routes have more vehicles
        if uneven_mode == 'down_left':
            # Assign weights: right & up high, left & down low
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.15,    0.35,   0.35,   0.15]  # sums to 1
        elif uneven_mode == 'right_down':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.35,    0.35,   0.15,   0.15]
        elif uneven_mode == 'right_up':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.35,    0.15,   0.15,   0.35]
        elif uneven_mode == 'left_up':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.15,    0.15,   0.35,   0.35]

        # one direction has more vehicles
        elif uneven_mode == 'up':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.05,    0.05,   0.05,   0.85]
        elif uneven_mode == 'down':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.05,    0.85,   0.05,   0.05]
        elif uneven_mode == 'left':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.05,    0.05,   0.85,   0.05]
        elif uneven_mode == 'right':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.85,    0.05,   0.05,   0.05]

        # alternate routes - up & down, left & right has more vehicles
        elif uneven_mode == 'up_down':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.15,    0.35,   0.15,   0.35]
        elif uneven_mode == 'left_right':
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.35,    0.15,   0.35,   0.15]
        
        # uniform probability
        else:
            directions  = ['right', 'down', 'left', 'up']
            weights     = [0.25,    0.25,   0.25,   0.25]

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
        # time.sleep(1) # 1 second interval between vehicle generations   

        # print(f"Generated vehicle {cnt}: {direction} lane {lane_number}")
        if cnt % 3 == 0:  # 3 vehicle in each second on average
            time.sleep(1) # 1 second interval between vehicle generations
