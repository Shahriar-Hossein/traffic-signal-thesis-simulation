# simulation.py

import random
import time

from config import (
    defaultGreen, defaultRed, defaultYellow,
    directionNumbers, vehicleTypes, defaultStop,
    noOfSignals
)
from vehicle import vehicles, Vehicle
from traffic_signal import TrafficSignal, signals
from utils import get_vehicle_counts


# for keeping vehicle count before cycle starts
vehicle_counts = {'right': 0, 'down': 0, 'left': 0, 'up': 0}

vehicleCountTexts = ["", "", "", ""]


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
            green_time = min(vehicle_count * 0.5, 10)

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
