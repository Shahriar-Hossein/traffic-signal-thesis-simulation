import pygame
import random
from datetime import datetime

from config import (
    speeds, x, y, stoppingGap, defaultStop,
    movingGap, stopLines, screenHeight, screenWidth
)
import state

from utils.logger import log_vehicle

vehicles = lambda: state.vehicles


class Vehicle(pygame.sprite.Sprite):
    def __init__(self, lane, vehicleClass, direction_number, direction):
        super().__init__()

        # ---------------------------------------------------------
        # BASIC ATTRIBUTES
        # ---------------------------------------------------------
        self.lane = lane
        self.vehicleClass = vehicleClass
        self.speed = speeds[vehicleClass]

        self.direction_number = direction_number      # 0=right,1=down,2=left,3=up
        self.direction = direction                    # "right", "down", "left", "up"

        # Spawn coordinates
        self.x = x[direction][lane]
        self.y = y[direction][lane]

        # Vehicle image
        image_path = f"images/{direction}/{vehicleClass}.png"
        self.image = pygame.image.load(image_path)

        # Vehicle state
        self.crossed = False
        self.index = None
        self.created_at = datetime.now()
        self.wait_start_time = None
        self.actual_wait_time = 0
        self.is_waiting = False

        # Detached flag (used when a vehicle leaves its lane to turn)
        self._detached = False

        # ---------------------------------------------------------
        # TURN LOGIC (3 LANES ONLY)
        # ---------------------------------------------------------
        # lane 0 = left turn
        # lane 1 = straight
        # lane 2 = right turn
        if lane == 0:
            self.turn = "left"
        elif lane == 2:
            self.turn = "right"
        else:
            self.turn = "straight"

        # Destination direction after turn
        if self.turn == "left":
            self.turn_dest_direction = {
                "up": "left",
                "left": "down",
                "down": "right",
                "right": "up",
            }[direction]

        elif self.turn == "right":
            self.turn_dest_direction = {
                "up": "right",
                "right": "down",
                "down": "left",
                "left": "up",
            }[direction]

        else:
            self.turn_dest_direction = None    # going straight

        # Random lane of the new road (0..2)
        self.turn_target_lane = random.randint(0, 2)

        # Turn blending animation
        self.turn_align_threshold = 4
        self.turn_blend_frames = 12
        self._turning = False
        self._turn_frame = 0

        # Coordinate where car should start turning (align axis)
        if self.turn != "straight":
            if direction in ("up", "down"):
                # vertical → horizontal: align Y to dest road's lane Y
                self.turn_target_coord = y[self.turn_dest_direction][self.turn_target_lane]
            else:
                # horizontal → vertical: align X to dest road's lane X
                self.turn_target_coord = x[self.turn_dest_direction][self.turn_target_lane]
        else:
            self.turn_target_coord = None

        # ---------------------------------------------------------
        # REGISTER VEHICLE
        # ---------------------------------------------------------
        state.vehicles[direction][lane].append(self)
        self.index = len(state.vehicles[direction][lane]) - 1

        # ---------------------------------------------------------
        # INITIAL STOP POSITION BEHIND PREVIOUS VEHICLE
        # ---------------------------------------------------------
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

        # ---------------------------------------------------------
        # ADJUST SPAWN POSITION (NO OVERLAP)
        # ---------------------------------------------------------
        img_size = (
            self.image.get_rect().width
            if direction in ("right", "left")
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

        # Add to sprite group
        state.vehicle_simulation.add(self)

    # -----------------------------------------------------------------
    # Helper: detach from current lane list (called when starting a turn)
    # -----------------------------------------------------------------
    def _detach_from_lane(self):
        if self._detached:
            return
        lane_list = state.vehicles[self.direction][self.lane]
        # Remove self from the lane list if present
        try:
            lane_list.remove(self)
        except ValueError:
            # not present; ignore
            pass
        else:
            # Re-index remaining vehicles in that lane
            for i, v in enumerate(lane_list):
                v.index = i
        self._detached = True
        # mark index as None while detached
        self.index = None

    # -----------------------------------------------------------------
    # Helper: attach to the new lane list (called when finishing a turn)
    # -----------------------------------------------------------------
    def _attach_to_new_lane(self):
        # append to new lane list (self.direction and self.lane should already be updated)
        lane_list = state.vehicles[self.direction][self.lane]
        lane_list.append(self)
        self.index = len(lane_list) - 1
        self._detached = False

    # =================================================================
    # RENDER
    # =================================================================
    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    # =================================================================
    # MOVEMENT LOGIC
    # =================================================================
    def move(self):
        width = self.image.get_width()
        height = self.image.get_height()

        # --------------------------------------------------------
        # TRAFFIC SIGNAL CHECK
        # --------------------------------------------------------
        green_go = (
            (self.direction == "right" and (state.currentGreen == 0 or self.crossed))
            or (self.direction == "down" and (state.currentGreen == 1 or self.crossed))
            or (self.direction == "left" and (state.currentGreen == 2 or self.crossed))
            or (self.direction == "up" and (state.currentGreen == 3 or self.crossed))
        ) and state.currentYellow == 0

        # --------------------------------------------------------
        # GET PREVIOUS VEHICLE (IF ATTACHED)
        # --------------------------------------------------------
        prev_vehicle = None
        if self.index is not None and self.index > 0:
            prev_vehicle = state.vehicles[self.direction][self.lane][self.index - 1]

        def prev_blocks(prev):
            if not prev:
                return False
            if getattr(prev, "_turning", False):
                return False
            if getattr(prev, "_detached", False):
                return False
            return True

        # --------------------------------------------------------
        # CROSS STOP LINE
        # --------------------------------------------------------
        if not self.crossed:
            if (
                (self.direction == "right" and self.x + width > stopLines[self.direction])
                or (self.direction == "down" and self.y + height > stopLines[self.direction])
                or (self.direction == "left" and self.x < stopLines[self.direction])
                or (self.direction == "up" and self.y < stopLines[self.direction])
            ):
                self.crossed = True
                log_vehicle(self)

        # --------------------------------------------------------
        # TURN ACTIVATION
        # --------------------------------------------------------
        if self.crossed and self.turn != "straight" and not self._turning:

            if self.direction in ("up", "down"):
                aligned = abs(self.y - self.turn_target_coord) <= self.turn_align_threshold
            else:
                aligned = abs(self.x - self.turn_target_coord) <= self.turn_align_threshold

            if aligned:
                # deterministic detach using index
                if self.index is not None:
                    lane_list = state.vehicles[self.direction][self.lane]
                    lane_list.pop(self.index)
                    for i, v in enumerate(lane_list):
                        v.index = i

                self._detached = True
                self.index = None
                self._turning = True
                self._turn_frame = 0

        # --------------------------------------------------------
        # TURN BLENDING
        # --------------------------------------------------------
        if self._turning:

            ratio = self._turn_frame / self.turn_blend_frames

            if self.direction in ("up", "down"):
                lateral = ratio * self.speed
                if self.turn == "left":
                    self.x -= lateral
                else:
                    self.x += lateral
            else:
                lateral = ratio * self.speed
                if self.turn == "left":
                    self.y += lateral
                else:
                    self.y -= lateral

            # continue forward motion
            if self.direction == "right":
                self.x += self.speed
            elif self.direction == "left":
                self.x -= self.speed
            elif self.direction == "down":
                self.y += self.speed
            elif self.direction == "up":
                self.y -= self.speed

            self._turn_frame += 1

            # TURN COMPLETE
            if self._turn_frame >= self.turn_blend_frames:

                # snap to exact lane coordinate
                if self.direction in ("up", "down"):
                    self.y = y[self.turn_dest_direction][self.turn_target_lane]
                else:
                    self.x = x[self.turn_dest_direction][self.turn_target_lane]

                # update direction & lane
                self.direction = self.turn_dest_direction
                self.lane = self.turn_target_lane

                # attach to new lane
                lane_list = state.vehicles[self.direction][self.lane]
                lane_list.append(self)
                self.index = len(lane_list) - 1
                self._detached = False

                # recompute stop position
                if self.index > 0:
                    prev = lane_list[self.index - 1]
                    prev_rect = prev.image.get_rect()

                    if self.direction == "right":
                        self.stop = prev.stop - prev_rect.width - stoppingGap
                    elif self.direction == "left":
                        self.stop = prev.stop + prev_rect.width + stoppingGap
                    elif self.direction == "down":
                        self.stop = prev.stop - prev_rect.height - stoppingGap
                    elif self.direction == "up":
                        self.stop = prev.stop + prev_rect.height + stoppingGap
                else:
                    self.stop = defaultStop[self.direction]

                self._turning = False
                self._turn_frame = 0

            return  # skip normal driving during turn

        # --------------------------------------------------------
        # NORMAL DRIVING
        # --------------------------------------------------------
        moving = False

        if self.direction == "right":
            can_move = (
                (self.x + width <= self.stop or self.crossed or green_go)
                and (
                    not prev_blocks(prev_vehicle)
                    or (self.x + width < prev_vehicle.x - movingGap)
                )
            )
            if can_move:
                self.x += self.speed
                moving = True

        elif self.direction == "down":
            can_move = (
                (self.y + height <= self.stop or self.crossed or green_go)
                and (
                    not prev_blocks(prev_vehicle)
                    or (self.y + height < prev_vehicle.y - movingGap)
                )
            )
            if can_move:
                self.y += self.speed
                moving = True

        elif self.direction == "left":
            can_move = (
                (self.x >= self.stop or self.crossed or green_go)
                and (
                    not prev_blocks(prev_vehicle)
                    or (self.x > prev_vehicle.x + prev_vehicle.image.get_width() + movingGap)
                )
            )
            if can_move:
                self.x -= self.speed
                moving = True

        elif self.direction == "up":
            can_move = (
                (self.y >= self.stop or self.crossed or green_go)
                and (
                    not prev_blocks(prev_vehicle)
                    or (self.y > prev_vehicle.y + prev_vehicle.image.get_height() + movingGap)
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
                self.actual_wait_time += (now - self.wait_start_time).total_seconds()
                self.wait_start_time = None
                self.is_waiting = False
        else:
            if not self.is_waiting:
                self.wait_start_time = now
                self.is_waiting = True

        # --------------------------------------------------------
        # OFF-SCREEN CLEANUP
        # --------------------------------------------------------

        if (
            self.x > screenWidth
            or self.x < -width
            or self.y > screenHeight
            or self.y < -height
        ):
            if self.index is not None:
                lane_list = state.vehicles[self.direction][self.lane]
                lane_list.pop(self.index)
                for i, v in enumerate(lane_list):
                    v.index = i
            self.kill()

    def get_type(self):
        return self.vehicleClass
