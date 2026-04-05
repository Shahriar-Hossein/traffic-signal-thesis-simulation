# Signal Timing Defaults
defaultGreen = {0: 12, 1: 12, 2: 12, 3: 12}
defaultRed = 150
defaultYellow = 5

# Vehicle Speeds (pixels per frame)
speeds = {
    'car': 2.0,
    'bus': 1.75,
    'truck': 1.5,
    'bike': 2.25
}

# Vehicle Types by ID
vehicleTypes = {
    0: 'car',
    1: 'bus',
    2: 'truck',
    3: 'bike'
}

# Direction Mapping
directionNumbers = {
    0: 'right',
    1: 'down',
    2: 'left',
    3: 'up'
}

# Starting X Coordinates for Each Lane per Direction
x = {
    'right': [0, 0, 0, 0],
    'down': [560, 610, 660, 560],
    'left': [1008, 1008, 1008, 1008],
    'up': [348, 392, 448, 450]
}

# Starting Y Coordinates for Each Lane per Direction
y = {
    'right': [310, 360, 410, 416],
    'down': [0, 0, 0, 0],
    'left': [510, 558, 605, 560],
    'up': [1000, 1000, 1000, 1000]
}

# Stop Lines (where vehicles halt before intersection)
stopLines = {
    'right': 240,
    'down': 240,
    'left': 780,
    'up': 750
}

# Default Vehicle Stop Positions (slightly before stop lines)
defaultStop = {
    'right': 230,
    'down': 230,
    'left': 790,
    'up': 760
}

# Signal Image Coordinates (adjust to match intersection image)
signalCoods = [
    (200, 210),  # Right
    (720, 155),  # Down
    (790, 710),  # Left
    (270, 770)   # Up
]

# Timer Text Coordinates (position of countdown texts)
signalTimerCoods = [
    (205, 190),
    (725, 135),
    (795, 690),
    (275, 750)
]

# Vehicle Count Display Positions
vehicleCountCoods = [
    (110, 270),
    (760, 210),
    (830, 770),
    (180, 830)
]

# Vehicle Spacing
stoppingGap = 15
movingGap = 15

# Simulation Controls
noOfSignals = 4

# Colors
black = (0, 0, 0)
white = (255, 255, 255)

# Display Settings
screenWidth = 1008
screenHeight = 1000
screenSize = (screenWidth, screenHeight)

# --- Turn Configuration ---

# Turn direction mapping per lane (from driver's perspective):
#   Lane 0 = left turn lane, Lane 1 = straight, Lane 2 = right turn lane
turnDirections = {
    'right': {0: 'up',    1: 'right', 2: 'down'},
    'down':  {0: 'left',  1: 'down',  2: 'right'},
    'left':  {0: 'up',    1: 'left',  2: 'down'},
    'up':    {0: 'left',  1: 'up',    2: 'right'},
}

# Probability that a vehicle in lane 0 or 2 will actually turn (0.0 to 1.0)
# Vehicles that don't turn will go straight even from turn lanes
turnProbability = 0.5

# How far past the stop line (pixels) before a turn begins
# Structure: direction -> turn_type -> {lane: offset}
# Each turning vehicle randomly picks one of 3 target lanes in the new direction
turnTriggerOffset = {
    'right': {
        'left_turn':  {0: 40,  1: 60,  2: 80},
        'right_turn': {0: 240, 1: 260, 2: 280},
    },
    'down': {
        'left_turn':  {0: 40,  1: 60,  2: 80},
        'right_turn': {0: 240, 1: 260, 2: 280},
    },
    'left': {
        'left_turn':  {0: 60,  1: 80,  2: 90},
        'right_turn': {0: 270, 1: 290, 2: 310},
    },
    'up': {
        'left_turn':  {0: 40,  1: 60,  2: 80},
        'right_turn': {0: 270, 1: 290, 2: 310},
    },
}

# Number of frames for the turn animation arc
# Structure: direction -> turn_type -> {lane: frames}
turnFrames = {
    'right': {
        'right_turn': {0: 30, 1: 35, 2: 40},
        'left_turn':  {0: 50, 1: 55, 2: 60},
    },
    'down': {
        'right_turn': {0: 30, 1: 35, 2: 40},
        'left_turn':  {0: 50, 1: 55, 2: 60},
    },
    'left': {
        'right_turn': {0: 30, 1: 35, 2: 40},
        'left_turn':  {0: 50, 1: 55, 2: 60},
    },
    'up': {
        'right_turn': {0: 30, 1: 35, 2: 40},
        'left_turn':  {0: 50, 1: 55, 2: 60},
    },
}
