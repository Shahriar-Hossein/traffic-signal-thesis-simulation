# main.py

import pygame
import sys
import threading
import time

import state

from config import (
    signalCoods, signalTimerCoods, vehicleCountCoods,
    directionNumbers,
    black, white, screenSize
)
from core.initializer import initialize
from core.generator import generateVehicles

from models.traffic_signal import signals

from utils.counters import get_vehicle_counts
from utils.logger import init_logger
from utils.draw import (
    draw_traffic_signals,
    draw_all_vehicles,
    draw_vehicle_count_texts,
    draw_inline_counts
)

def start_simulation_threads():
    """
    Starts initialization and vehicle generation in separate threads.
    """
    init_logger(state.duration, state.uneven_mode)
    threading.Thread(
        target=initialize, name="InitializationThread", daemon=True
    ).start()
    threading.Thread(
        target=generateVehicles,
        name="VehicleGeneratorThread",
        kwargs={'uneven_mode': state.uneven_mode},
        daemon=True
    ).start()


def main():
    pygame.init()
    pygame.font.init()
    clock = pygame.time.Clock()
    # normal approach, fixed timer
    state.currentMode = "fixed" 
    # Our appraoch, priority based
    # state.currentMode = "priority" 
    # Fairness based approach
    state.currentMode = "fairness_priority" 

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


    start_time = time.time()

    while True:
        # Check simulation time
        elapsed_time = time.time() - start_time
        if elapsed_time >= state.duration:
            print("Simulation time complete. Exiting...")
            state.running = False
            pygame.quit()
            sys.exit()

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

if __name__ == "__main__":
    main()