import pygame
from config import (
    speeds, x, y, stoppingGap, defaultStop, 
    movingGap, directionNumbers, stopLines,
    currentGreen, currentYellow
)

# Group to manage and render all vehicles
simulation = pygame.sprite.Group()

# Dictionary to hold vehicles per lane and direction
vehicles = {
    'right': {0: [], 1: [], 2: [], 3: [], 'crossed': 0}, 
    'down':  {0: [], 1: [], 2: [], 3: [], 'crossed': 0}, 
    'left':  {0: [], 1: [], 2: [], 3: [], 'crossed': 0}, 
    'up':    {0: [], 1: [], 2: [], 3: [], 'crossed': 0}
}

class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction):
        super().__init__()
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction

        # Set starting coordinates
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0

        # Load vehicle image
        image_path = f"images/{direction}/{vehicleClass}.png"
        self.image = pygame.image.load(image_path)

        # Add to lane
        vehicles[direction][lane].append(self)
        self.index = len(vehicles[direction][lane]) - 1

        # Determine stop position
        if self.index > 0 and not vehicles[direction][lane][self.index - 1].crossed:
            prev = vehicles[direction][lane][self.index - 1]
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

        simulation.add(self)

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    def move(self):
        rect = self.image.get_rect()
        width, height = rect.width, rect.height

        green_go = (
            (self.direction == 'right' and currentGreen == 0) or
            (self.direction == 'down' and currentGreen == 1) or
            (self.direction == 'left' and currentGreen == 2) or
            (self.direction == 'up' and currentGreen == 3)
        ) and currentYellow == 0

        prev_vehicle = None
        if self.index > 0:
            prev_vehicle = vehicles[self.direction][self.lane][self.index - 1]

        if self.direction == 'right':
            if not self.crossed and self.x + width > stopLines[self.direction]:
                self.crossed = 1

            if (self.x + width <= self.stop or self.crossed or green_go):
                if not prev_vehicle or (self.x + width < prev_vehicle.x - movingGap):
                    self.x += self.speed

        elif self.direction == 'down':
            if not self.crossed and self.y + height > stopLines[self.direction]:
                self.crossed = 1

            if (self.y + height <= self.stop or self.crossed or green_go):
                if not prev_vehicle or (self.y + height < prev_vehicle.y - movingGap):
                    self.y += self.speed

        elif self.direction == 'left':
            if not self.crossed and self.x < stopLines[self.direction]:
                self.crossed = 1

            if (self.x >= self.stop or self.crossed or green_go):
                if not prev_vehicle or (self.x > prev_vehicle.x + prev_vehicle.image.get_rect().width + movingGap):
                    self.x -= self.speed

        elif self.direction == 'up':
            if not self.crossed and self.y < stopLines[self.direction]:
                self.crossed = 1

            if (self.y >= self.stop or self.crossed or green_go):
                if not prev_vehicle or (self.y > prev_vehicle.y + prev_vehicle.image.get_rect().height + movingGap):
                    self.y -= self.speed
