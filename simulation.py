import random
import time
import threading
import pygame
import sys
import heapq


pygame.init()
pygame.font.init()
simulation = pygame.sprite.Group()

# Default values of signal timers
defaultGreen = {0:10, 1:10, 2:10, 3:10}
defaultRed = 150
defaultYellow = 5

signals = []
noOfSignals = 4
currentGreen = 0   # Indicates which signal is green currently
nextGreen = (currentGreen+1)%noOfSignals    # Indicates which signal will turn green next
currentYellow = 0   # Indicates whether yellow signal is on or off 

speeds = {'car':1, 'bus':.5, 'truck':.5, 'bike':1}  # average speeds of vehicles
# speeds = {'car':2, 'bus':1, 'truck':1, 'bike':2}  # average speeds of vehicles
# speeds = {'car':0.65, 'bus':0.4, 'truck':0.4, 'bike':.75}  # average speeds of vehicles
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


# vehicles = {'right': {0:[], 1:[], 2:[], 'crossed':0}, 'down': {0:[], 1:[], 2:[], 'crossed':0}, 'left': {0:[], 1:[], 2:[], 'crossed':0}, 'up': {0:[], 1:[], 2:[], 'crossed':0}}
vehicles = {'right': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 'down': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 'left': {0:[], 1:[], 2:[], 3:[], 'crossed':0}, 'up': {0:[], 1:[], 2:[], 3:[], 'crossed':0}}
vehicleTypes = {0:'car', 1:'bus', 2:'truck', 3:'bike'}
directionNumbers = {0:'right', 1:'down', 2:'left', 3:'up'}

# for keeping vehicle count before cycle starts
vehicle_counts = {'right': 0, 'down': 0, 'left': 0, 'up': 0}

# Font (reuse or redefine if needed)
font = pygame.font.Font(None, 28)
vehicleCountTexts = ["", "", "", ""]


# Adjust these to align with traffic light poles in the background
signalCoods = [(200,210), (720,155), (790,710), (270,770)]

# Adjust timer positions near signals
signalTimerCoods = [(205,190), (725,135), (795,690), (275,750)]

# Align vehicle count displays better
vehicleCountCoods = [(110, 270), (760, 210), (830, 770), (180, 830)]

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
# stops = {'right': [580,580,580], 'down': [320,320,320], 'left': [810,810,810], 'up': [545,545,545]}

# Gap between vehicles
stoppingGap = 15    # stopping gap
movingGap = 15   # moving gap
class TrafficSignal:
    def __init__(self, red, yellow, green):
        self.red = red
        self.yellow = yellow
        self.green = green
        self.signalText = ""
        
class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction):
        pygame.sprite.Sprite.__init__(self)
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0
        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1
        path = "images/" + direction + "/" + vehicleClass + ".png"
        self.image = pygame.image.load(path)

        if(len(vehicles[direction][lane])>1 and vehicles[direction][lane][self.index-1].crossed==0):    # if more than 1 vehicle in the lane of vehicle before it has crossed stop line
            if(direction=='right'):
                self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].image.get_rect().width - stoppingGap         # setting stop coordinate as: stop coordinate of next vehicle - width of next vehicle - gap
            elif(direction=='left'):
                self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].image.get_rect().width + stoppingGap
            elif(direction=='down'):
                self.stop = vehicles[direction][lane][self.index-1].stop - vehicles[direction][lane][self.index-1].image.get_rect().height - stoppingGap
            elif(direction=='up'):
                self.stop = vehicles[direction][lane][self.index-1].stop + vehicles[direction][lane][self.index-1].image.get_rect().height + stoppingGap
        else:
            self.stop = defaultStop[direction]
            
        # Set new starting and stopping coordinate
        if(direction=='right'):
            temp = self.image.get_rect().width + stoppingGap    
            x[direction][lane] -= temp
        elif(direction=='left'):
            temp = self.image.get_rect().width + stoppingGap
            x[direction][lane] += temp
        elif(direction=='down'):
            temp = self.image.get_rect().height + stoppingGap
            y[direction][lane] -= temp
        elif(direction=='up'):
            temp = self.image.get_rect().height + stoppingGap
            y[direction][lane] += temp
        simulation.add(self)

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    def move(self):
        if(self.direction=='right'):
            if(self.crossed==0 and self.x+self.image.get_rect().width>stopLines[self.direction]):   # if the image has crossed stop line now
                self.crossed = 1
            if((self.x+self.image.get_rect().width<=self.stop or self.crossed == 1 or (currentGreen==0 and currentYellow==0)) and (self.index==0 or self.x+self.image.get_rect().width<(vehicles[self.direction][self.lane][self.index-1].x - movingGap))):                
            # (if the image has not reached its stop coordinate or has crossed stop line or has green signal) and (it is either the first vehicle in that lane or it is has enough gap to the next vehicle in that lane)
                self.x += self.speed  # move the vehicle
        elif(self.direction=='down'):
            if(self.crossed==0 and self.y+self.image.get_rect().height>stopLines[self.direction]):
                self.crossed = 1
            if((self.y+self.image.get_rect().height<=self.stop or self.crossed == 1 or (currentGreen==1 and currentYellow==0)) and (self.index==0 or self.y+self.image.get_rect().height<(vehicles[self.direction][self.lane][self.index-1].y - movingGap))):                
                self.y += self.speed
        elif(self.direction=='left'):
            if(self.crossed==0 and self.x<stopLines[self.direction]):
                self.crossed = 1
            if((self.x>=self.stop or self.crossed == 1 or (currentGreen==2 and currentYellow==0)) and (self.index==0 or self.x>(vehicles[self.direction][self.lane][self.index-1].x + vehicles[self.direction][self.lane][self.index-1].image.get_rect().width + movingGap))):                
                self.x -= self.speed   
        elif(self.direction=='up'):
            if(self.crossed==0 and self.y<stopLines[self.direction]):
                self.crossed = 1
            if((self.y>=self.stop or self.crossed == 1 or (currentGreen==3 and currentYellow==0)) and (self.index==0 or self.y>(vehicles[self.direction][self.lane][self.index-1].y + vehicles[self.direction][self.lane][self.index-1].image.get_rect().height + movingGap))):                
                self.y -= self.speed

# Initialization of signals with default values
def initialize():
    ts1 = TrafficSignal(0, defaultYellow, defaultGreen[0])
    signals.append(ts1)
    ts2 = TrafficSignal(ts1.red+ts1.yellow+ts1.green, defaultYellow, defaultGreen[1])
    signals.append(ts2)
    ts3 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[2])
    signals.append(ts3)
    ts4 = TrafficSignal(defaultRed, defaultYellow, defaultGreen[3])
    signals.append(ts4)
    repeat()

# Helper function to count uncrossed vehicles for each direction
# def get_vehicle_counts():
#     counts = {}
#     for dir_name in directionNumbers.values():
#         count = 0
#         for lane in range(3):
#             count += sum(1 for vehicle in vehicles[dir_name][lane] if vehicle.crossed == 0)
#         counts[dir_name] = count
#     return counts

def get_vehicle_counts():
    counts = {}
    for i in range(4):  # 0:right, 1:down, 2:left, 3:up
        direction = directionNumbers[i]
        count = sum(1 for lane in range(3) for v in vehicles[direction][lane] if not v.crossed)
        counts[direction] = count
    return counts

# Dynamic queue generation based on vehicle count
def generate_signal_queue():
    vehicle_counts = get_vehicle_counts()
    sorted_gates = sorted(vehicle_counts.items(), key=lambda x: x[1], reverse=True)
    return [list(directionNumbers.keys())[list(directionNumbers.values()).index(direction)] for direction, _ in sorted_gates]

def repeat():
    global currentGreen, currentYellow

    while True:
        vehicle_counts_snapshot = get_vehicle_counts()
        signalQueue = sorted(vehicle_counts_snapshot.items(), key=lambda x: x[1], reverse=True)
        signalQueue = [list(directionNumbers.keys())[list(directionNumbers.values()).index(direction)] for direction, _ in signalQueue]

        for currentGreen in signalQueue:
            vehicle_count = get_vehicle_counts()[directionNumbers[currentGreen]]
            green_time = min(vehicle_count * 0.5, 90)

            signals[currentGreen].green = int(green_time)
            while signals[currentGreen].green > 0:
                updateValues()
                time.sleep(1)

            currentYellow = 1
            for i in range(3):
                for vehicle in vehicles[directionNumbers[currentGreen]][i]:
                    vehicle.stop = defaultStop[directionNumbers[currentGreen]]
            while signals[currentGreen].yellow > 0:
                updateValues()
                time.sleep(1)
            currentYellow = 0

            signals[currentGreen].green = defaultGreen[currentGreen]
            signals[currentGreen].yellow = defaultYellow
            signals[currentGreen].red = defaultRed

        repeat()  # Start the next cycle after queue is emptied

# This adjusted `repeat` method now dynamically assigns green times based on real-time vehicle counts,
# serves directions based on demand using FIFO logic, and resets every full cycle.

# Update values of the signal timers after every second
def updateValues():
    for i in range(0, noOfSignals):
        if(i==currentGreen):
            if(currentYellow==0):
                signals[i].green-=1
            else:
                signals[i].yellow-=1
        else:
            signals[i].red-=1

# Generating vehicles in the simulation
def generateVehicles():
    while(True):
        vehicle_type = random.randint(0,3)
        temp = random.randint(0,99)
        direction_number = 0
        dist = [25,50,75,100]
        if(temp<dist[0]):
            direction_number = 0
        elif(temp<dist[1]):
            direction_number = 1
        elif(temp<dist[2]):
            direction_number = 2
        elif(temp<dist[3]):
            direction_number = 3
        
        #  Decide the number of lanes
        max_lane_number = 3
        # if(direction_number%2):
        #     max_lane_number = 4
        lane_number = random.randint(0,max_lane_number-1)
        
        Vehicle(lane_number, vehicleTypes[vehicle_type], direction_number, directionNumbers[direction_number])
        time.sleep(1)

class Main:
    thread1 = threading.Thread(name="initialization",target=initialize, args=())    # initialization
    thread1.daemon = True
    thread1.start()

    # Colours 
    black = (0, 0, 0)
    white = (255, 255, 255)

    # Screensize 
    screenWidth = 1008
    screenHeight = 1000
    screenSize = (screenWidth, screenHeight)

    # Setting background image i.e. image of intersection
    background = pygame.image.load('images/city_intersection.png')

    screen = pygame.display.set_mode(screenSize)
    pygame.display.set_caption("SIMULATION")

    # Loading signal images and font
    redSignal = pygame.image.load('images/signals/red.png')
    yellowSignal = pygame.image.load('images/signals/yellow.png')
    greenSignal = pygame.image.load('images/signals/green.png')
    font = pygame.font.Font(None, 30)

    thread2 = threading.Thread(name="generateVehicles",target=generateVehicles, args=())    # Generating vehicles
    thread2.daemon = True
    thread2.start()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                sys.exit()

        screen.blit(background,(0,0))   # display background in simulation
        for i in range(0,noOfSignals):  # display signal and set timer according to current status: green, yello, or red
            if(i==currentGreen):
                if(currentYellow==1):
                    signals[i].signalText = signals[i].yellow
                    screen.blit(yellowSignal, signalCoods[i])
                else:
                    signals[i].signalText = signals[i].green
                    screen.blit(greenSignal, signalCoods[i])
            else:
                if(signals[i].red<=10):
                    signals[i].signalText = signals[i].red
                else:
                    signals[i].signalText = "---"
                screen.blit(redSignal, signalCoods[i])
        signalTexts = ["","","",""]

        # display signal timer
        for i in range(0,noOfSignals):  
            signalTexts[i] = font.render(str(signals[i].signalText), True, white, black)
            screen.blit(signalTexts[i],signalTimerCoods[i])

        # display the vehicles
        for vehicle in simulation:  
            screen.blit(vehicle.image, [vehicle.x, vehicle.y])
            vehicle.move()
        vehicle_counts = get_vehicle_counts()
        vehicleCountTexts = ["", "", "", ""]
        for i in range(noOfSignals):
            direction = directionNumbers[i]
            vehicleCountTexts[i] = font.render(f"Count: {vehicle_counts[direction]}", True, white, black)
            screen.blit(vehicleCountTexts[i], vehicleCountCoods[i])
        pygame.display.update()


Main()