# Signal Timing Defaults
defaultGreen = {0: 10, 1: 10, 2: 10, 3: 10}
defaultRed = 10
defaultYellow = 10

# Vehicle Speeds (pixels per frame)
speeds = {
    'car': 1,
    'bus': 0.5,
    'truck': 0.5,
    'bike': 1
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
    'down': [660, 610, 560, 560],
    'left': [1500, 1500, 1500, 1500],
    'up': [350, 400, 450, 450]
}

# Starting Y Coordinates for Each Lane per Direction
y = {
    'right': [310, 360, 410, 416],
    'down': [0, 0, 0, 0],
    'left': [610, 560, 510, 560],
    'up': [1400, 1400, 1400, 1400]
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
currentGreen = 0
nextGreen = (currentGreen + 1) % noOfSignals
currentYellow = 0

# Colors
black = (0, 0, 0)
white = (255, 255, 255)

# Display Settings
screenWidth = 1008
screenHeight = 1000
screenSize = (screenWidth, screenHeight)
