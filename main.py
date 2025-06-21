# main.py

import pygame
import sys

from utils import get_vehicle_counts
from config import (
    signalCoods, signalTimerCoods, vehicleCountCoods,
    directionNumbers,
    black, white, screenSize
)
from draw_utils import draw_traffic_signals, draw_all_vehicles, draw_vehicle_count_texts, draw_inline_counts
from traffic_signal import signals
from simulation import start_simulation_threads
import state

# vehicle_simulation = lambda: state.vehicle_simulation

pygame.init()
pygame.font.init()
clock = pygame.time.Clock()
start_simulation_threads()

# Setting background image i.e. image of intersection
background = pygame.image.load('images/city_intersection.png')

screen = pygame.display.set_mode(screenSize)
pygame.display.set_caption("Traffic Signal Control Thesis")

# Loading signal images and font
redSignal = pygame.image.load('images/signals/red.png')
yellowSignal = pygame.image.load('images/signals/yellow.png')
greenSignal = pygame.image.load('images/signals/green.png')
font = pygame.font.Font(None, 30)


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()

    screen.blit(background,(0,0))   # display background in simulation

    draw_traffic_signals(screen, font, signals, state.currentGreen, 
        state.currentYellow, redSignal, yellowSignal, greenSignal,
        signalCoods, signalTimerCoods, black, white)

    draw_all_vehicles(screen, state.vehicle_simulation)

    draw_vehicle_count_texts(screen, font, get_vehicle_counts(),
        directionNumbers, vehicleCountCoods, black, white)
    
    draw_inline_counts(screen, font, get_vehicle_counts(), directionNumbers)
    
    pygame.display.update()
    clock.tick(60)  # Cap to 60 FPS

