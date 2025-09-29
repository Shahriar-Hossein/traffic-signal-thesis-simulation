import pygame
from logger import log_vehicle
from config import (
    speeds, x, y, stoppingGap, defaultStop, 
    movingGap, stopLines,
)
import state
from datetime import datetime

vehicles = lambda: state.vehicles

class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction):
        super().__init__()
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction

        self.created_at = datetime.now()
        self.wait_start_time = None  # When it first had to stop
        self.actual_wait_time = 0    # Total time spent waiting
        self.is_waiting = False      # Whether it's currently waiting

        # Set starting coordinates
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0

        # Load vehicle image
        image_path = f"images/{direction}/{vehicleClass}.png"
        self.image = pygame.image.load(image_path)

        # Add to lane
        state.vehicles[direction][lane].append(self)
        self.index = len(state.vehicles[direction][lane]) - 1

        # Determine stop position
        if self.index > 0 and not state.vehicles[direction][lane][self.index - 1].crossed:
            prev = state.vehicles[direction][lane][self.index - 1]
            prev_rect = prev.image.get_rect()
            if direction == 'right':
                self.stop = prev.stop - prev_rect.width - stoppingGap
            elif direction == 'left':
                self.stop = prev.stop + prev_rect.width + stoppingGap
            elif direction == 'down':
                self.stop = prev.stop - prev_rect.height - stoppingGap
            elif direction == 'up':
                self.stop = prev.stop + prev_rect.height + stoppingGap
        else:
            self.stop = defaultStop[direction]

        # Update lane start for next vehicle
        img_size = self.image.get_rect().width if direction in ['right', 'left'] else self.image.get_rect().height
        offset = img_size + stoppingGap

        if direction == 'right':
            x[direction][lane] -= offset
        elif direction == 'left':
            x[direction][lane] += offset
        elif direction == 'down':
            y[direction][lane] -= offset
        elif direction == 'up':
            y[direction][lane] += offset

        state.vehicle_simulation.add(self)

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    def move(self):
        rect = self.image.get_rect()
        width, height = rect.width, rect.height

        green_go = (
            (self.direction == 'right' and state.currentGreen == 0) or
            (self.direction == 'down' and state.currentGreen == 1) or
            (self.direction == 'left' and state.currentGreen == 2) or
            (self.direction == 'up' and state.currentGreen == 3)
        ) and state.currentYellow == 0

        prev_vehicle = None
        if self.index > 0:
            prev_vehicle = state.vehicles[self.direction][self.lane][self.index - 1]

        # Check if vehicle crossed stop line and log it
        if not self.crossed:
            if (
                (self.direction == 'right' and self.x + width > stopLines[self.direction]) or
                (self.direction == 'down' and self.y + height > stopLines[self.direction]) or
                (self.direction == 'left' and self.x < stopLines[self.direction]) or
                (self.direction == 'up' and self.y < stopLines[self.direction])
            ):
                self.crossed = 1
                log_vehicle(self)

        # Determine if vehicle should move or wait
        moving = False
        if self.direction == 'right':
            can_move = (self.x + width <= self.stop or self.crossed or green_go) and \
                    (not prev_vehicle or (self.x + width < prev_vehicle.x - movingGap))
            if can_move:
                self.x += self.speed
                moving = True

        elif self.direction == 'down':
            can_move = (self.y + height <= self.stop or self.crossed or green_go) and \
                    (not prev_vehicle or (self.y + height < prev_vehicle.y - movingGap))
            if can_move:
                self.y += self.speed
                moving = True

        elif self.direction == 'left':
            can_move = (self.x >= self.stop or self.crossed or green_go) and \
                    (not prev_vehicle or (self.x > prev_vehicle.x + prev_vehicle.image.get_rect().width + movingGap))
            if can_move:
                self.x -= self.speed
                moving = True

        elif self.direction == 'up':
            can_move = (self.y >= self.stop or self.crossed or green_go) and \
                    (not prev_vehicle or (self.y > prev_vehicle.y + prev_vehicle.image.get_rect().height + movingGap))
            if can_move:
                self.y -= self.speed
                moving = True

        # Wait time tracking
        now = datetime.now()
        if moving:
            # If previously waiting, accumulate waited time
            if self.is_waiting:
                waited = (now - self.wait_start_time).total_seconds()
                self.actual_wait_time += waited
                self.is_waiting = False
                self.wait_start_time = None
        else:
            # Vehicle stopped: start waiting timer if not already waiting
            if not self.is_waiting:
                self.wait_start_time = now
                self.is_waiting = True
    
    def get_type(self):
        # Returns the class of the vehicle (e.g., car, bike, truck)
        return self.vehicleClass
