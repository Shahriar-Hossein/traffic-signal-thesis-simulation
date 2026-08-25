# state.py

import pygame

# All vehicles categorized by direction and lane
vehicles = {
    'right': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 
    'down': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 
    'left': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 
    'up': {0:[], 1:[], 2:[], 3:[], 'crossed':0}
}

# Waiting time for each direction
waiting_time = {
    'right': 0,
    'down': 0,
    'left': 0,
    'up': 0
}

# Group for rendering & managing vehicles
vehicle_simulation = pygame.sprite.Group()

# Current signal states (which one is green / yellow)
currentGreen = 0
currentYellow = 0

# priority mode for our approach, fixed for regular approach
# priority approach, dynamic timer
# currentMode = "priority"
# normal approach, fixed timer
currentMode = "fixed"


# for exit logic
running = True

# --- How the run ends ---
# 'time'     -> stop when the wall clock reaches `duration` (original behaviour)
# 'vehicles' -> generate `target_vehicle_count` vehicles, stop once all of them
#               have crossed the stop line
# run_mode = 'time'
run_mode = 'vehicles'

# --- 'vehicles' mode settings ---
# Number of vehicles to generate for the run.
target_vehicle_count = 500
# Safety cap in seconds. If a vehicle wedges and the target is never reached,
# the run aborts here instead of hanging forever (batch runs depend on this).
count_mode_timeout = 1800

# --- Live counters (written at runtime, not settings) ---
# Owned by the generator thread only.
vehicles_generated = 0
# Owned by the main/render thread only (incremented where a vehicle crosses).
# Each counter has a single writer, so no lock is needed.
vehicles_crossed = 0

# Why the run ended: 'duration' | 'target_reached' | 'timeout' | 'user_quit'
stop_reason = None

# current traffic condition set by the vehicle generator ('high'/'medium'/'low')
traffic_condition = None

uneven_mode = 'even'
# uneven_mode = 'up'
# uneven_mode = 'top_right'
# uneven_mode = 'bottom_left'
# uneven_mode = 'up_down'
# uneven_mode = 'left_right'


# simulation time (only used when run_mode == 'time')
# duration = 60 # 1 minute
# duration = 120 # 2 minutes
# duration = 180 # 3 minutes
# duration = 240 # 4 minutes
# duration = 300 # 5 minutes
duration = 600 # 10 minutes
# duration = 900 # 15 minutes
# duration = 1200 # 20 minutes
# duration = 1500 # 25 minutes
# duration = 1800 # 30 minutes