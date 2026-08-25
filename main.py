# main.py
# test github
import pygame
import sys
import threading
import time
from datetime import datetime

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
from utils.logger import init_logger, write_run_meta
from utils.draw import (
    draw_traffic_signals,
    draw_all_vehicles,
    draw_vehicle_count_texts,
    draw_inline_counts,
    draw_buildings
)

# Seconds to keep rendering after the last vehicle has crossed, so in-flight
# turns finish on screen.  Purely cosmetic — every vehicle is already logged.
COUNT_MODE_DRAIN_SEC = 1.5


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


def should_stop(elapsed):
    """
    Decide whether the run is over, and why.

    Returns a stop reason string, or None to keep running.
    """
    if state.run_mode == 'vehicles':
        target = state.target_vehicle_count
        if state.vehicles_generated >= target and state.vehicles_crossed >= target:
            return 'target_reached'
        if elapsed >= state.count_mode_timeout:
            return 'timeout'
        return None

    return 'duration' if elapsed >= state.duration else None


def shutdown(reason, elapsed, started_at):
    """
    Stop the background threads, record how the run ended, and exit.
    """
    state.stop_reason = reason
    state.running = False

    if state.run_mode == 'vehicles':
        print(
            f"Simulation ended ({reason}): "
            f"{state.vehicles_crossed}/{state.target_vehicle_count} vehicles "
            f"crossed in {elapsed:.1f}s"
        )
        write_run_meta(
            target_vehicle_count=state.target_vehicle_count,
            vehicles_generated=state.vehicles_generated,
            vehicles_crossed=state.vehicles_crossed,
            duration_sec=round(elapsed, 2),
            stop_reason=reason,
            started_at=started_at.strftime("%Y-%m-%d %H:%M:%S"),
            ended_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    else:
        print(f"Simulation ended ({reason}) after {elapsed:.1f}s")

    pygame.quit()
    sys.exit()


def main():
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

    if state.run_mode == 'vehicles':
        print(
            f"Run mode: vehicles | target = {state.target_vehicle_count} "
            f"| controller = {state.currentMode} | load = {state.uneven_mode} "
            f"| timeout = {state.count_mode_timeout}s"
        )
    else:
        print(
            f"Run mode: time | duration = {state.duration}s "
            f"| controller = {state.currentMode} | load = {state.uneven_mode}"
        )

    start_time = time.time()
    started_at = datetime.now()
    target_reached_at = None

    while True:
        # Check whether the run is over
        elapsed_time = time.time() - start_time
        stop_reason = should_stop(elapsed_time)

        if stop_reason == 'target_reached':
            # Let in-flight turns finish before closing the window
            if target_reached_at is None:
                target_reached_at = time.time()
            elif time.time() - target_reached_at >= COUNT_MODE_DRAIN_SEC:
                shutdown(stop_reason, elapsed_time, started_at)
        elif stop_reason is not None:
            shutdown(stop_reason, elapsed_time, started_at)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                shutdown('user_quit', elapsed_time, started_at)

        screen.blit(background,(0,0))   # display background in simulation

        # draw_buildings(screen)

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