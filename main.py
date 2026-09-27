# main.py
import argparse
import os
import pygame
import sys
import threading
from datetime import datetime

import state
import config as runtime_config

from config import (
    signalCoods, signalTimerCoods, vehicleCountCoods,
    directionNumbers,
    black, white, screenSize
)
from core.initializer import initialize
from core.generator import generateVehicles
from core.plan import load_plan, check_plan_against_config
from core import runclock
from core.controllers import NAMES as CONTROLLER_NAMES

from models.traffic_signal import signals

from utils.counters import get_vehicle_counts
from utils.logger import finalize_phase, init_logger, write_run_meta
from utils.draw import (
    draw_traffic_signals,
    draw_all_vehicles,
    draw_vehicle_count_texts,
    draw_inline_counts
)

# Seconds to keep rendering after the last vehicle has crossed, so in-flight
# turns finish on screen.  Purely cosmetic — every vehicle is already logged.
RENDER_DRAIN_SEC = 1.5

# Window over which the worst frame rate is measured.  Per-frame instantaneous
# FPS is far too noisy to gate on; a one-second floor is what a viewer (and a
# vehicle, since physics runs in the renderer) actually feels.
FPS_SAMPLE_WINDOW_SEC = 1.0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Replay one planned traffic run.")
    parser.add_argument("--plan", required=True, help="Scheduled vehicle plan.")
    parser.add_argument("--controller", choices=list(CONTROLLER_NAMES), required=True)
    parser.add_argument("--pair-id", required=True)
    parser.add_argument("--arm", required=True)
    parser.add_argument("--paired-root", help="Root for paired plans and logs.")
    parser.add_argument("--fixed-green", type=int, choices=(12, 24))
    parser.add_argument("--timeout", type=int, help="Per-arm safety cap in seconds.")
    return parser.parse_args(argv)


def apply_args(args):
    state.currentMode = args.controller
    state.pair_id = args.pair_id
    state.arm_label = args.arm
    if args.paired_root is not None:
        state.paired_root = os.path.abspath(args.paired_root)
    if args.timeout is not None:
        state.count_mode_timeout = args.timeout

    load_plan_into_state(args.plan)
    if state.pair_id != state.vehicle_plan['header']['plan_id']:
        raise ValueError("--pair-id must match the loaded plan's plan_id")
    if args.fixed_green is not None:
        if state.currentMode != 'fixed':
            raise ValueError("--fixed-green requires --controller fixed")
        runtime_config.defaultGreen = {index: args.fixed_green for index in range(4)}


def load_plan_into_state(path):
    """
    Load a replay plan and make the run obey it.

    Aborts if the plan was written against different config: replaying a plan
    under a changed turn probability or arrival-rate table produces traffic
    that is not what the plan says it is, and the comparison it feeds would be
    invalid without anything visibly going wrong.
    """
    try:
        plan = load_plan(path)
    except (OSError, ValueError) as e:
        # A bad plan is a setup mistake, not a crash — say what is wrong and
        # stop, rather than dumping a traceback from inside the loader.
        print(f"ERROR: {e}")
        sys.exit(2)

    problems = check_plan_against_config(plan)
    if problems:
        print(
            f"ERROR: plan {path} disagrees with the current config — "
            "replaying it would be a silently invalid comparison:"
        )
        for problem in problems:
            print(f"  - {problem}")
        sys.exit(2)

    header = plan['header']
    state.vehicle_plan_path = path
    state.vehicle_plan = plan
    state.target_vehicle_count = header['target_vehicle_count']
    state.uneven_mode = header['uneven_mode']


def start_simulation_threads():
    """
    Starts initialization and vehicle generation in separate threads.
    """
    init_logger()
    # Origin for every timestamp in this run; must precede the threads that
    # read it.
    runclock.start()
    threading.Thread(
        target=initialize, name="InitializationThread", daemon=True
    ).start()
    threading.Thread(
        target=generateVehicles,
        name="VehicleGeneratorThread",
        daemon=True
    ).start()


def should_stop(elapsed):
    target = state.target_vehicle_count
    if state.vehicles_generated >= target and state.vehicles_crossed >= target:
        return 'target_reached'
    if elapsed >= state.count_mode_timeout:
        return 'timeout'
    return None


def shutdown(reason, elapsed, started_at, fps_stats=None):
    """
    Stop the background threads, record how the run ended, and exit.

    Everything written here runs on the main thread, before sys.exit: the
    shutdown path has no thread join and no flush barrier, so a sidecar field
    computed on the generator thread could simply never be written.
    """
    state.stop_reason = reason
    state.running = False

    # The controller is a daemon thread: it is killed where it stands, which
    # is usually inside the very phase that served the last vehicles.  That
    # phase is written here, once, marked censored — otherwise every run loses
    # its final green, and every crossing served by it looks like a crossing
    # that happened outside any green.
    censored = finalize_phase(round(elapsed, 4))

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
        last_crossing_sec=(
            round(state.last_crossing_sec, 4)
            if state.last_crossing_sec is not None else None
        ),
        stop_reason=reason,
        final_phase_censored=censored is not None,
        started_at=started_at.strftime("%Y-%m-%d %H:%M:%S"),
        ended_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        **(fps_stats or {}),
    )

    pygame.quit()
    sys.exit()


class FpsTracker:
    """
    Frame-rate adherence for the paired-run validity gate.

    This is not cosmetic instrumentation: physics runs inside the renderer
    (`draw_all_vehicles` calls `vehicle.move()`), so an arm that renders more
    slowly literally has slower vehicles.  Left unmeasured, that confound
    looks exactly like a controller effect.
    """

    def __init__(self):
        self.frames_total = 0
        self._started_at = runclock.elapsed()
        self._window_started_at = self._started_at
        self._last_frame_at = self._started_at
        self._window_frames = 0
        # The whole series, not just its extremes: two arms can share a mean
        # and still have run their physics at different rates at the moments
        # that mattered.
        self.windows = []
        # Each window's actual start and end on the run clock. A window closes
        # when a rendered frame finally arrives, not on a schedule, so after a
        # stall two arms' window `k` no longer describe the same seconds.
        # Comparing sample index alone cannot see that; these boundaries can.
        self.window_bounds = []

    def tick(self):
        self.frames_total += 1
        self._window_frames += 1

        now = runclock.elapsed()
        self._last_frame_at = now
        elapsed = now - self._window_started_at
        if elapsed >= FPS_SAMPLE_WINDOW_SEC:
            self.windows.append(round(self._window_frames / elapsed, 2))
            self.window_bounds.append(
                [round(self._window_started_at, 4), round(now, 4)])
            self._window_started_at = now
            self._window_frames = 0

    def stats(self, elapsed):
        windows = list(self.windows)
        bounds = [list(bound) for bound in self.window_bounds]
        # Shutdown occurs after the final sleep, without another physics frame.
        remainder = self._last_frame_at - self._window_started_at
        if self._window_frames and remainder > 0:
            windows.append(round(self._window_frames / remainder, 2))
            bounds.append([round(self._window_started_at, 4), round(self._last_frame_at, 4)])
        covered = sum(end - start for start, end in bounds)
        return {
            "frames_total": self.frames_total,
            "fps_mean": round(self.frames_total / elapsed, 2) if elapsed else None,
            "fps_min": min(windows) if windows else None,
            "fps_window_sec": FPS_SAMPLE_WINDOW_SEC,
            "fps_windows": windows,
            "fps_window_bounds": bounds,
            "fps_telemetry_start_sec": round(self._started_at, 4),
            "fps_telemetry_end_sec": round(self._last_frame_at, 4),
            "fps_covered_sec": round(covered, 4),
        }


def main(argv=None):
    apply_args(parse_args(argv))

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

    if state.pair_id is not None:
        print(
            f"Paired replay: pair = {state.pair_id} | arm = {state.arm_label} "
            f"| controller = {state.currentMode} | plan = {state.vehicle_plan_path}"
        )

    print(
        f"Planned run: {state.target_vehicle_count} vehicles "
        f"| controller = {state.currentMode} | load = {state.uneven_mode} "
        f"| timeout = {state.count_mode_timeout}s"
    )

    started_at = datetime.now()
    target_reached_at = None
    fps = FpsTracker()

    while True:
        # Check whether the run is over
        elapsed_time = runclock.elapsed()
        stop_reason = should_stop(elapsed_time)

        if stop_reason == 'target_reached':
            # Let in-flight turns finish before closing the window
            if target_reached_at is None:
                target_reached_at = elapsed_time
            elif elapsed_time - target_reached_at >= RENDER_DRAIN_SEC:
                shutdown(stop_reason, elapsed_time, started_at,
                         fps.stats(elapsed_time))
        elif stop_reason is not None:
            shutdown(stop_reason, elapsed_time, started_at,
                     fps.stats(elapsed_time))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                shutdown('user_quit', elapsed_time, started_at,
                         fps.stats(elapsed_time))

        screen.blit(background,(0,0))   # display background in simulation


        draw_traffic_signals(screen, font, signals, state.currentGreen,
            state.currentYellow, redSignal, yellowSignal, greenSignal,
            signalCoods, signalTimerCoods, black, white)

        draw_all_vehicles(screen, state.vehicle_simulation)

        draw_vehicle_count_texts(screen, font, get_vehicle_counts(),
            directionNumbers, vehicleCountCoods, black, white)

        draw_inline_counts(screen, font, get_vehicle_counts(), directionNumbers)

        pygame.display.update()
        fps.tick()
        clock.tick(60)  # Cap to 60 FPS

if __name__ == "__main__":
    main()
