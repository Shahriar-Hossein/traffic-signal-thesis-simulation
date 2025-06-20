# main.py

import pygame
import threading
import sys

from simulation import initialize, generateVehicles
from utils import get_vehicle_counts
from config import (
    signalCoods, signalTimerCoods, vehicleCountCoods,
    directionNumbers, noOfSignals, currentYellow, currentGreen,
    black, white, screenSize
)
from vehicle import vehicles, simulation
from traffic_signal import signals

pygame.init()
pygame.font.init()


thread1 = threading.Thread(name="initialization",target=initialize, args=())    # initialization
thread1.daemon = True
thread1.start()


# Setting background image i.e. image of intersection
background = pygame.image.load('images/city_intersection.png')

screen = pygame.display.set_mode(screenSize)
pygame.display.set_caption("Traffic Signal Control Thesis")

# Loading signal images and font
redSignal = pygame.image.load('images/signals/red.png')
yellowSignal = pygame.image.load('images/signals/yellow.png')
greenSignal = pygame.image.load('images/signals/green.png')
font = pygame.font.Font(None, 30)

thread2 = threading.Thread(name="generateVehicles",target=generateVehicles, args=())    # Generating vehicles
thread2.daemon = True
thread2.start()

cafBuilding = pygame.image.load('images/buildings/cafe_building.png')

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()

    screen.blit(background,(0,0))   # display background in simulation
    
    # screen.blit(cafBuilding, (150,150))

    # render traffic signal lights and timers
    for i in range(0,noOfSignals):  
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

