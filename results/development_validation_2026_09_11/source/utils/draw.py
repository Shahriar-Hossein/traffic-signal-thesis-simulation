# draw_utils.py

import pygame
from typing import Dict, Tuple

def draw_traffic_signals(
    screen: pygame.Surface,
    font: pygame.font.Font,
    signals: list,
    current_green: int,
    current_yellow: int,
    red_img: pygame.Surface,
    yellow_img: pygame.Surface,
    green_img: pygame.Surface,
    signal_coords: list,
    timer_coords: list,
    black: Tuple[int, int, int],
    white: Tuple[int, int, int]
):
    """
    Draw traffic lights and their countdown timers.
    """
    for i, signal in enumerate(signals):
        if i == current_green:
            if current_yellow:
                signal.signalText = signal.yellow
                screen.blit(yellow_img, signal_coords[i])
            else:
                signal.signalText = signal.green
                screen.blit(green_img, signal_coords[i])
        else:
            signal.signalText = signal.red if signal.red <= 10 else "---"
            screen.blit(red_img, signal_coords[i])

    for i, signal in enumerate(signals):
        timer_surface = font.render(str(signal.signalText), True, white, black)
        screen.blit(timer_surface, timer_coords[i])


def draw_all_vehicles(screen: pygame.Surface, simulation_group: pygame.sprite.Group):
    """
    Draw and move all vehicles in the simulation group.
    """
    for vehicle in simulation_group:
        screen.blit(vehicle.image, (vehicle.x, vehicle.y))
        vehicle.move()


def draw_vehicle_count_texts(
    screen: pygame.Surface,
    font: pygame.font.Font,
    vehicle_counts: Dict[str, int],
    direction_map: Dict[int, str],
    count_coords: list,
    black: Tuple[int, int, int],
    white: Tuple[int, int, int]
):
    """
    Display vehicle counts near each direction.
    """
    for i, direction in direction_map.items():
        text = font.render(f"Count: {vehicle_counts[direction]}", True, white, black)
        screen.blit(text, count_coords[i])


def draw_inline_counts(
    screen: pygame.Surface,
    font: pygame.font.Font,
    vehicle_counts: Dict[str, int],
    direction_map: Dict[int, str],
    position: Tuple[int, int] = (50, 950),
    black: Tuple[int, int, int] = (0, 0, 0),
    white: Tuple[int, int, int] = (255, 255, 255)
):
    """
    Display vehicle counts inline at the bottom.
    """
    line = " | ".join(
        f"{direction.capitalize()}: {vehicle_counts[direction]}"
        for direction in direction_map.values()
    )
    text_surface = font.render(line, True, white, black)
    screen.blit(text_surface, position)


def draw_buildings(screen: pygame.Surface, building_size: Tuple[int, int] = (150, 150)):
    """
    Draw scaled building images on the four corners of the screen.
    
    Args:
        screen: pygame.Surface to draw on
        building_size: Tuple of (width, height) for scaled building images
    """
    # Building image paths and their corner positions (top-left of image)
    buildings = [
        ('images/buildings/appartment_building.png', (0, 0)),  # Top-left
        ('images/buildings/cafe_building.png', (screen.get_width() - building_size[0], 0)),  # Top-right
        ('images/buildings/commercial_building.png', (0, screen.get_height() - building_size[1])),  # Bottom-left
        ('images/buildings/mall_building.png', (screen.get_width() - building_size[0], screen.get_height() - building_size[1]))  # Bottom-right
    ]
    
    for image_path, position in buildings:
        try:
            building_img = pygame.image.load(image_path)
            # Scale the building image to the specified size
            scaled_building = pygame.transform.scale(building_img, building_size)
            screen.blit(scaled_building, position)
        except pygame.error as e:
            print(f"Warning: Could not load building image from {image_path}: {e}")
