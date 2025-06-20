# Default values of signal timers
defaultGreen = {0:10, 1:10, 2:10, 3:10}
defaultRed = 150
defaultYellow = 5

speeds = {'car':1, 'bus':.5, 'truck':.5, 'bike':1}  # average speeds of vehicles
# speeds = {'car':2, 'bus':1, 'truck':1, 'bike':2}  # average speeds of vehicles
# speeds = {'car':0.65, 'bus':0.4, 'truck':0.4, 'bike':.75}  # average speeds of vehicles

vehicleTypes = {0:'car', 1:'bus', 2:'truck', 3:'bike'}
directionNumbers = {0:'right', 1:'down', 2:'left', 3:'up'}

# Coordinates of vehicles' start
x = {
    'right':[0, 0, 0, 0], 
    'down':[660, 610, 560, 560], 
    'left':[1500, 1500, 1500, 1500], 
    'up':[350, 400, 450, 450]
}
y = {
    'right':[310, 360, 410, 416], 
    'down':[0, 0, 0, 0], 
    'left':[610, 560, 510, 560], 
    'up':[1400, 1400, 1400, 1400]
}

# Adjust stop lines for better traffic flow alignment
stopLines = {
    'right': 240,  # x position where vehicles moving right should stop
    'down': 240,   # y position for vehicles moving down
    'left': 780,   # x position for vehicles moving left
    'up': 750      # y position for vehicles moving up
}

defaultStop = {
    'right': 230,  # slightly before stop line
    'down': 230,
    'left': 790,
    'up': 760
}

# UI Elements
# Adjust these to align with traffic light poles in the background
signalCoods = [(200,210), (720,155), (790,710), (270,770)]
# Adjust timer positions near signals
signalTimerCoods = [(205,190), (725,135), (795,690), (275,750)]
# Align vehicle count displays better
vehicleCountCoods = [(110, 270), (760, 210), (830, 770), (180, 830)]

# Gap between vehicles
stoppingGap = 15    # stopping gap
movingGap = 15   # moving gap

noOfSignals = 4
currentGreen = 0   # Indicates which signal is green currently
nextGreen = (currentGreen+1)%noOfSignals    # Indicates which signal will turn green next
currentYellow = 0   # Indicates whether yellow signal is on or off 


# Colours 
black = (0, 0, 0)
white = (255, 255, 255)

# Screensize 
screenWidth = 1008
screenHeight = 1000
screenSize = (screenWidth, screenHeight)
