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

currentMode = "fixed"
running = True
target_vehicle_count = 0
count_mode_timeout = 1800
vehicle_plan_path = None
vehicle_plan = None
pair_id = None
arm_label = None
paired_root = None

# --- Live counters (written at runtime, not settings) ---
# Owned by the generator thread only.
vehicles_generated = 0
# Replay adherence, owned by the generator thread, read by main on shutdown.
# How late each release was against its planned offset; the paired analyzer
# refuses a pair whose arms did not honour the plan equally well.
release_count = 0
release_drift_sum_ms = 0.0
release_drift_max_ms = 0.0
# Run-clock time of the most recent crossing. Reported separately from the
# run duration, which also covers the display drain after the last crossing.
last_crossing_sec = None
# Owned by the main/render thread only (incremented where a vehicle crosses).
# Each counter has a single writer, so no lock is needed.
vehicles_crossed = 0

# Why the planned run ended.
stop_reason = None

# current traffic condition set by the vehicle generator ('high'/'medium'/'low')
traffic_condition = None

uneven_mode = 'even'
