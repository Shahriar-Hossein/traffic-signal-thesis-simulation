# Signal Timing Defaults
defaultGreen = {0: 12, 1: 12, 2: 12, 3: 12}
defaultRed = 150
defaultYellow = 4

# Vehicle Speeds (pixels per frame)
speeds = {
    'car': 2.25,
    'bus': 2.0,
    'truck': 1.80,
    'bike': 2.5
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
    'right': [10, 10, 10, 0],
    'down': [560, 610, 660, 560],
    'left': [998, 998, 998, 1008],
    'up': [348, 392, 448, 450]
}

# Starting Y Coordinates for Each Lane per Direction
y = {
    'right': [310, 360, 410, 416],
    'down': [10, 10, 10, 0],
    'left': [510, 558, 605, 560],
    'up': [990, 990, 990, 1000]
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
