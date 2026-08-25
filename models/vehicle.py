import pygame
import math
import random

from datetime import datetime

from config import (
    speeds, x, y, stoppingGap, defaultStop, 
    movingGap, stopLines,
    turnDirections, turnFrames,
    turnProbability,
)
import state

from utils.logger import log_vehicle


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

        # Turn-related properties
        possible_turn = turnDirections[direction][lane]
        # Randomly decide whether this vehicle actually turns
        if possible_turn != direction and random.random() < turnProbability:
            self.turn_direction = possible_turn
            self.will_turn = True
            self.target_turn_lane = random.randint(0, 2)  # pick random lane in new direction
        else:
            self.turn_direction = direction
            self.will_turn = False
            self.target_turn_lane = 0
        self.turning_active = False
        self.turn_complete = False
        self.turn_progress = 0.0
        self.original_image = self.image.copy() if self.will_turn else None
        self.original_speed = self.speed
        self._turn_center_x = 0.0
        self._turn_center_y = 0.0
        if self.will_turn:
            turn_type = self._get_turn_type()
            self.turn_total_frames = turnFrames[direction][turn_type].get(
                self.target_turn_lane, 40
            )
            # Dynamically compute when to start turning so the arc
            # naturally ends at the correct target lane coordinate.
            self._dynamic_trigger_offset = self._compute_trigger_offset()
        else:
            self.turn_total_frames = 0
            self._dynamic_trigger_offset = 0

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
        if self.index > 0 and not state.vehicles[direction][lane][self.index - 1].crossed:
            prev = state.vehicles[direction][lane][self.index - 1]
            if direction == 'right':
                self.x = prev.x - offset - 100
            elif direction == 'left':
                self.x = prev.x + offset + 100
            elif direction == 'down':
                self.y = prev.y - offset - 100
            elif direction == 'up':
                self.y = prev.y + offset + 100
        
        state.vehicle_simulation.add(self)

    def render(self, screen):
        screen.blit(self.image, (self.x, self.y))

    # --- Turn helper constants and methods ---

    _DIRECTION_VECTORS = {
        'right': (1, 0),
        'down': (0, 1),
        'left': (-1, 0),
        'up': (0, -1)
    }

    _DIRECTION_ANGLES = {
        'right': 0,
        'up': 90,
        'left': 180,
        'down': 270
    }

    def _get_turn_type(self):
        """Returns 'right_turn', 'left_turn', or 'straight'."""
        dirs = ['right', 'down', 'left', 'up']
        orig_idx = dirs.index(self.direction)
        target_idx = dirs.index(self.turn_direction)
        diff = (target_idx - orig_idx) % 4
        if diff == 1:
            return 'right_turn'
        if diff == 3:
            return 'left_turn'
        return 'straight'

    def _direction_vector(self, direction):
        return self._DIRECTION_VECTORS[direction]

    def _compute_trigger_offset(self):
        """Compute trigger offset so the arc naturally ends at the target lane.

        The vehicle's movement axis before the turn becomes the perpendicular
        axis of the new direction.  By choosing when the turn starts, we
        control where the arc deposits the vehicle on that axis.
        """
        N = self.turn_total_frames
        orig_dx, orig_dy = self._DIRECTION_VECTORS[self.direction]
        new_dx, new_dy = self._DIRECTION_VECTORS[self.turn_direction]

        # Sum displacement on each axis over the full arc
        total_dx = 0.0
        total_dy = 0.0
        for i in range(1, N + 1):
            t = min(i / N, 1.0)
            of = math.cos(t * math.pi / 2)
            nf = math.sin(t * math.pi / 2)
            total_dx += self.speed * (of * orig_dx + nf * new_dx)
            total_dy += self.speed * (of * orig_dy + nf * new_dy)

        # Load target image to get dimensions
        target_img = pygame.image.load(
            f"images/{self.turn_direction}/{self.vehicleClass}.png"
        )
        target_rect = target_img.get_rect()
        current_rect = self.image.get_rect()

        # Identify axis quantities depending on original direction
        if self.direction in ('right', 'left'):
            half_size = current_rect.width / 2.0
            total_perp = total_dx
            target_center = (
                x[self.turn_direction][self.target_turn_lane]
                + target_rect.width / 2.0
            )
        else:  # 'down', 'up'
            half_size = current_rect.height / 2.0
            total_perp = total_dy
            target_center = (
                y[self.turn_direction][self.target_turn_lane]
                + target_rect.height / 2.0
            )

        stop_line = stopLines[self.direction]
        # right/down: trigger fires when pos > stopLine + offset  → sign = +1
        # left/up:    trigger fires when pos < stopLine - offset  → sign = -1
        sign = 1 if self.direction in ('right', 'down') else -1

        offset = sign * (target_center - stop_line - half_size - total_perp)
        return max(offset, 10)  # ensure a sensible minimum

    def _reached_turn_trigger(self):
        """Check if vehicle has entered the intersection far enough to begin turning."""
        offset = self._dynamic_trigger_offset
        if self.direction == 'right':
            return self.x > stopLines['right'] + offset
        elif self.direction == 'down':
            return self.y > stopLines['down'] + offset
        elif self.direction == 'left':
            return self.x < stopLines['left'] - offset
        elif self.direction == 'up':
            return self.y < stopLines['up'] - offset
        return False

    def _get_turn_angle(self, t):
        """Get the relative rotation angle for the current turn progress."""
        start = self._DIRECTION_ANGLES[self.direction]
        end = self._DIRECTION_ANGLES[self.turn_direction]
        diff = (end - start + 180) % 360 - 180
        return diff * t

    def _execute_turn(self):
        """Execute one frame of the smooth turning arc."""
        # On first frame, initialize center tracking
        if self.turn_progress == 0.0:
            rect = self.image.get_rect()
            self._turn_center_x = self.x + rect.width / 2.0
            self._turn_center_y = self.y + rect.height / 2.0

            # Pre-load target direction image for use at completion
            self._turn_target_image = pygame.image.load(
                f"images/{self.turn_direction}/{self.vehicleClass}.png"
            )

        self.turn_progress += 1.0 / self.turn_total_frames
        t = min(self.turn_progress, 1.0)

        # Smooth arc: cosine fades out original direction, sine fades in new
        orig_factor = math.cos(t * math.pi / 2)
        new_factor = math.sin(t * math.pi / 2)

        orig_dx, orig_dy = self._direction_vector(self.direction)
        new_dx, new_dy = self._direction_vector(self.turn_direction)

        dx = self.speed * (orig_factor * orig_dx + new_factor * new_dx)
        dy = self.speed * (orig_factor * orig_dy + new_factor * new_dy)

        self._turn_center_x += dx
        self._turn_center_y += dy

        # Rotate sprite image for visual smoothness
        angle = self._get_turn_angle(t)
        rotated = pygame.transform.rotate(self.original_image, angle)
        new_rect = rotated.get_rect(
            center=(int(self._turn_center_x), int(self._turn_center_y))
        )
        self.image = rotated
        self.x = new_rect.left
        self.y = new_rect.top

        # Turn completed — snap to exact lane coordinate (only a few
        # pixels off due to frame-boundary overshoot at trigger time).
        if self.turn_progress >= 1.0:
            self.turn_complete = True
            self.image = self._turn_target_image
            new_rect = self.image.get_rect()
            if self.turn_direction in ('right', 'left'):
                self.y = y[self.turn_direction][self.target_turn_lane]
                self.x = int(self._turn_center_x - new_rect.width / 2.0)
            else:
                self.x = x[self.turn_direction][self.target_turn_lane]
                self.y = int(self._turn_center_y - new_rect.height / 2.0)

    def _find_nearest_ahead_post_turn(self):
        """Find the nearest vehicle ahead in the new direction after a turn."""
        new_dir = self.turn_direction
        rect = self.image.get_rect()
        my_w, my_h = rect.width, rect.height

        # Perpendicular-axis tolerance for "same lane" matching
        lane_tolerance = 25

        if new_dir in ('right', 'left'):
            my_lane_coord = self.y
        else:
            my_lane_coord = self.x

        nearest = None
        nearest_dist = float('inf')

        for vehicle in state.vehicle_simulation:
            if vehicle is self:
                continue

            # Determine effective direction of the other vehicle
            if getattr(vehicle, 'turn_complete', False):
                eff_dir = vehicle.turn_direction
            elif getattr(vehicle, 'turning_active', False):
                continue  # skip vehicles mid-turn
            else:
                eff_dir = vehicle.direction

            if eff_dir != new_dir:
                continue

            # Check if in same lane (perpendicular axis within tolerance)
            if new_dir in ('right', 'left'):
                other_lane_coord = vehicle.y
                if abs(other_lane_coord - my_lane_coord) > lane_tolerance:
                    continue
                if new_dir == 'right' and vehicle.x > self.x:
                    dist = vehicle.x - (self.x + my_w)
                elif new_dir == 'left' and vehicle.x < self.x:
                    dist = self.x - (vehicle.x + vehicle.image.get_rect().width)
                else:
                    continue
            else:
                other_lane_coord = vehicle.x
                if abs(other_lane_coord - my_lane_coord) > lane_tolerance:
                    continue
                if new_dir == 'down' and vehicle.y > self.y:
                    dist = vehicle.y - (self.y + my_h)
                elif new_dir == 'up' and vehicle.y < self.y:
                    dist = self.y - (vehicle.y + vehicle.image.get_rect().height)
                else:
                    continue

            if dist < nearest_dist:
                nearest_dist = dist
                nearest = vehicle

        return nearest, nearest_dist

    # --- Main movement logic ---

    def move(self):
        rect = self.image.get_rect()
        width, height = rect.width, rect.height

        # --- Post-turn: move in new direction with gap checking ---
        if self.turn_complete:
            dx, dy = self._direction_vector(self.turn_direction)

            # Check for vehicles ahead to prevent overlapping
            ahead, gap_dist = self._find_nearest_ahead_post_turn()
            if ahead is not None and gap_dist <= movingGap:
                return  # wait — too close to vehicle ahead

            self.x += self.speed * dx
            self.y += self.speed * dy
            # Only remove if vehicle already crossed the stop line and left view
            if self.crossed and self._is_out_of_bounds():
                self._remove_from_simulation()
                return
            return

        # --- Active turning: execute turn arc ---
        if self.crossed and self.will_turn and not self.turn_complete:
            if not self.turning_active:
                if self._reached_turn_trigger():
                    self.turning_active = True
                    self.turn_progress = 0.0
            if self.turning_active:
                self._execute_turn()
                # After executing a turn frame, only remove if it had crossed
                if self.crossed and self._is_out_of_bounds():
                    self._remove_from_simulation()
                    return
                return

        green_go = (
            (self.direction == 'right' and state.currentGreen == 0) or
            (self.direction == 'down' and state.currentGreen == 1) or
            (self.direction == 'left' and state.currentGreen == 2) or
            (self.direction == 'up' and state.currentGreen == 3)
        ) and state.currentYellow == 0

        # Find the nearest non-turning vehicle ahead in the same lane.
        # When the vehicle in front has turned away, this vehicle naturally
        # resumes its own original speed (no artificial blocker).
        prev_vehicle = None
        if self.index > 0:
            for i in range(self.index - 1, -1, -1):
                candidate = state.vehicles[self.direction][self.lane][i]
                # Only skip vehicles whose turn is fully complete (they've
                # left this lane).  Vehicles that are mid-turn are still
                # physically in the way and must block following traffic.
                if not getattr(candidate, 'turn_complete', False):
                    prev_vehicle = candidate
                    break

        # Speed recovery: restore original speed only when the direct
        # predecessor has fully completed its turn and left the lane.
        # While the vehicle ahead is mid-turn it is still physically
        # blocking, so do not speed up.
        if self.speed < self.original_speed:
            if prev_vehicle is None or not getattr(prev_vehicle, 'turning_active', False):
                self.speed = self.original_speed

        # Check if vehicle crossed stop line and log it
        if not self.crossed:
            if (
                (self.direction == 'right' and self.x + width > stopLines[self.direction]) or
                (self.direction == 'down' and self.y + height > stopLines[self.direction]) or
                (self.direction == 'left' and self.x < stopLines[self.direction]) or
                (self.direction == 'up' and self.y < stopLines[self.direction])
            ):
                self.crossed = 1
                state.vehicles_crossed += 1
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
        # After normal movement handling, remove vehicles that exited the screen
        # but only if they already crossed the stop line earlier
        if self.crossed and self._is_out_of_bounds():
            self._remove_from_simulation()

    def get_type(self):
        # Returns the class of the vehicle (e.g., car, bike, truck)
        return self.vehicleClass

    def _is_out_of_bounds(self, margin: int = 100) -> bool:
        """Return True if vehicle is well outside the display bounds."""
        rect = self.image.get_rect()
        left = self.x
        top = self.y
        right = self.x + rect.width
        bottom = self.y + rect.height

        from config import screenWidth, screenHeight

        if right < -margin or left > screenWidth + margin or bottom < -margin or top > screenHeight + margin:
            return True
        return False

    def _remove_from_simulation(self):
        """Remove vehicle from sprite groups and lane lists, and fix indices."""
        try:
            state.vehicle_simulation.remove(self)
        except Exception:
            pass

        lane_list = state.vehicles.get(self.direction, {}).get(self.lane)
        if lane_list is None:
            return

        # Remove by identity if present
        try:
            idx = lane_list.index(self)
        except ValueError:
            return

        lane_list.pop(idx)

        # Update indices for remaining vehicles in the lane
        for i, v in enumerate(lane_list):
            v.index = i
