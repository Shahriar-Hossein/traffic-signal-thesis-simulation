# state.py

import pygame

# All vehicles categorized by direction and lane
vehicles = {
    'right': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 
    'down': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 
    'left': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 
    'up': {0:[], 1:[], 2:[], 3:[], 'crossed':0}
}

# Group for rendering & managing vehicles
vehicle_simulation = pygame.sprite.Group()

# Current signal states (which one is green / yellow)
currentGreen = 0
currentYellow = 0

# priority mode for our approach, fixed for regular approach
currentMode = "priority"

# for exit logic
running = True

# uneven_mode = 'even'
# uneven_mode = 'one_direction'
uneven_mode = 'top_right'
# uneven_mode = 'bottom_left'


# simulation time
# duration = 300
# duration = 180
duration = 120
# duration = 60
# duration = 240