import pygame
import random
from datetime import datetime

from config import (
    speeds, x, y, stoppingGap, defaultStop,
    movingGap, stopLines
)
import state

from utils.logger import log_vehicle

vehicles = lambda: state.vehicles


class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction):
        super().__init__()
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]
        self.direction_number = direction_number
        self.direction = direction

        # TURN PARAMETERS (SIMPLE VERSION)
        self.turn = "straight"            # left / right / straight
        self.turn_dest_direction = None   # where it will face after turn
        self.turn_target_lane = random.randint(0, 2)     # which lane of the new road
        self.turn_target_coord = None     # coordinate of that lane
        self.turn_align_threshold = 4
        self.turn_blend_frames = 12
        self._turning = False
        self._turn_frame = 0
        self.turn_lane = random.randint(0, 2)

        self.created_at = datetime.now()
        self.wait_start_time = None
        self.actual_wait_time = 0
        self.is_waiting = False

        # Starting coordinates
        self.x = x[direction][lane]
        self.y = y[direction][lane]
        self.crossed = 0

        # Load image
        image_path = f"images/{direction}/{vehicleClass}.png"
        self.image = pygame.image.load(image_path)

        # -----------------------------------------
        # 1. DECIDE TURN TYPE BASED ON SPAWN LANE
        # -----------------------------------------
        lanes_count = len(x[direction])

        if lane == 0:
            self.turn = "left"
        elif lane == lanes_count - 1:
            self.turn = "right"
        else:
            self.turn = "straight"

        # -----------------------------------------
        # 2. DETERMINE DESTINATION DIRECTION (AT SPAWN)
        # -----------------------------------------
        if self.turn == "left":
            self.turn_dest_direction = {
                "up": "left",
                "down": "right",
                "left": "down",
                "right": "up",
            }[direction]


        elif self.turn == "right":
            self.turn_dest_direction = {
                "up": "right",
                "down": "left",
                "left": "up",
                "right": "down",
            }[direction]

        # Straight means no turning
        else:
            self.turn_dest_direction = None

        # -----------------------------------------
        # 3. PICK RANDOM TARGET LANE (AT SPAWN)
        # -----------------------------------------
        if self.turn != "straight":

            # If original direction was vertical, turning means align y
            if direction in ("up", "down"):
                self.turn_target_coord = y[self.turn_dest_direction][self.turn_target_lane]
            # If original direction was horizontal, align x
            else:
                self.turn_target_coord = x[self.turn_dest_direction][self.turn_target_lane]

        # Add to state vehicles
        state.vehicles[direction][lane].append(self)
        self.index = len(state.vehicles[direction][lane]) - 1

        # -----------------------------------------
        # Set stop position behind previous vehicle
        # -----------------------------------------
        if self.index > 0 and not state.vehicles[direction][lane][self.index - 1].crossed:
            prev = state.vehicles[direction][lane][self.index - 1]
            prev_rect = prev.image.get_rect()

            if direction == "right":
                self.stop = prev.stop - prev_rect.width - stoppingGap
            elif direction == "left":
                self.stop = prev.stop + prev_rect.width + stoppingGap
            elif direction == "down":
                self.stop = prev.stop - prev_rect.height - stoppingGap
            elif direction == "up":
                self.stop = prev.stop + prev_rect.height + stoppingGap
        else:
            self.stop = defaultStop[direction]

        # -----------------------------------------
        # Adjust spawn position behind previous car
        # -----------------------------------------
        img_size = (
            self.image.get_rect().width
            if direction in ["right", "left"]
            else self.image.get_rect().height
        )

        offset = img_size + stoppingGap
        if self.index > 0 and not state.vehicles[direction][lane][self.index - 1].crossed:
            prev = state.vehicles[direction][lane][self.index - 1]

            if direction == "right":
                self.x = prev.x - offset - 100
            elif direction == "left":
                self.x = prev.x + offset + 100
            elif direction == "down":
                self.y = prev.y - offset - 100
            elif direction == "up":
                self.y = prev.y + offset + 100

        state.vehicle_simulation.add(self)

    # ================================================================
    # RENDER
    # ================================================================
    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    # ================================================================
    # MOVEMENT + TURNING
    # ================================================================
    def move(self):
        rect = self.image.get_rect()
        width, height = rect.width, rect.height

        green_go = (
            (self.direction == "right" and ( state.currentGreen == 0 or self.crossed ))
            or (self.direction == "down" and ( state.currentGreen == 1 or self.crossed  ) )
            or (self.direction == "left" and ( state.currentGreen == 2 or self.crossed ))
            or (self.direction == "up" and ( state.currentGreen == 3 or self.crossed ))
        ) and state.currentYellow == 0

        prev_vehicle = None
        if self.index > 0:
            prev_vehicle = state.vehicles[self.direction][self.lane][self.index - 1]

        # --------------------------------------------------------
        # STOP LINE CROSSING
        # --------------------------------------------------------
        if not self.crossed:
            if (
                (self.direction == "right" and self.x + width > stopLines[self.direction])
                or (self.direction == "down" and self.y + height > stopLines[self.direction])
                or (self.direction == "left" and self.x < stopLines[self.direction])
                or (self.direction == "up" and self.y < stopLines[self.direction])
            ):
                self.crossed = 1
                log_vehicle(self)

        # --------------------------------------------------------
        # TURN START TRIGGERED ONCE AFTER CROSSING
        # --------------------------------------------------------
        if ( self.crossed and self.turn != "straight" and not self._turning ):
            # If original direction was vertical, turning means align y
            if self.direction in ("up", "down"):
                if( self.turn_target_coord == self.y ):
                    self._turning = True
                    self._turn_frame = 0
            # If original direction was horizontal, align x
            else:
                if( self.turn_target_coord == self.x ):
                    self._turning = True
                    self._turn_frame = 0


        # --------------------------------------------------------
        # TURN BLENDING (CURVE)
        # --------------------------------------------------------
        if self._turning:
            blend_ratio = self._turn_frame / self.turn_blend_frames

            # vertical → horizontal
            if self.direction in ("up", "down"):
                if self.turn == "left":
                    self.x -= blend_ratio * self.speed
                elif self.turn == "right":
                    self.x += blend_ratio * self.speed

            # horizontal → vertical
            if self.direction in ("left", "right"):
                if self.turn == "left":
                    self.y += blend_ratio * self.speed
                elif self.turn == "right":
                    self.y -= blend_ratio * self.speed

            self._turn_frame += 1

            if self._turn_frame >= self.turn_blend_frames:
                # finalize turn
                self.direction = self.turn_dest_direction
                self.lane = self.turn_target_lane
                self._turning = False

        # --------------------------------------------------------
        # NORMAL DRIVING
        # --------------------------------------------------------
        moving = False

        if self.direction == "right":
            can_move = (
                (self.x + width <= self.stop or self.crossed or green_go)
                and (not prev_vehicle or self.x + width < prev_vehicle.x - movingGap)
            )
            if can_move:
                self.x += self.speed
                moving = True

        elif self.direction == "down":
            can_move = (
                (self.y + height <= self.stop or self.crossed or green_go)
                and (not prev_vehicle or self.y + height < prev_vehicle.y - movingGap)
            )
            if can_move:
                self.y += self.speed
                moving = True

        elif self.direction == "left":
            can_move = (
                (self.x >= self.stop or self.crossed or green_go)
                and (
                    not prev_vehicle
                    or self.x > prev_vehicle.x + prev_vehicle.image.get_rect().width + movingGap
                )
            )
            if can_move:
                self.x -= self.speed
                moving = True

        elif self.direction == "up":
            can_move = (
                (self.y >= self.stop or self.crossed or green_go)
                and (
                    not prev_vehicle
                    or self.y > prev_vehicle.y + prev_vehicle.image.get_rect().height + movingGap
                )
            )
            if can_move:
                self.y -= self.speed
                moving = True

        # --------------------------------------------------------
        # WAIT TIME TRACKING
        # --------------------------------------------------------
        now = datetime.now()
        if moving:
            if self.is_waiting:
                waited = (now - self.wait_start_time).total_seconds()
                self.actual_wait_time += waited
                self.is_waiting = False
                self.wait_start_time = None
        else:
            if not self.is_waiting:
                self.wait_start_time = now
                self.is_waiting = True

    def get_type(self):
        return self.vehicleClass
