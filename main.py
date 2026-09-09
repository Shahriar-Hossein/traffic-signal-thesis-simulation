# main.py
# test github
import argparse
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
from core.plan import load_plan, check_plan_against_config

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

# Window over which the worst frame rate is measured.  Per-frame instantaneous
# FPS is far too noisy to gate on; a one-second floor is what a viewer (and a
# vehicle, since physics runs in the renderer) actually feels.
FPS_SAMPLE_WINDOW_SEC = 1.0


def parse_args(argv=None):
    """
    Command-line overrides for the settings that normally live in state.py.

    Every flag defaults to None and is only applied when actually given, so
    `python3 main.py` with no arguments behaves exactly as it did before this
    existed.  That is the regression guarantee, not a nicety.
    """
    parser = argparse.ArgumentParser(
        description="Run the traffic-signal simulation."
    )
    parser.add_argument(
        "--plan",
        help="Replay a vehicle plan file instead of generating random traffic. "
             "Implies --run-mode vehicles; the count comes from the plan.",
    )
    parser.add_argument(
        "--controller",
        choices=["fixed", "priority", "fairness_priority"],
        help="Signal controller to run (default: state.currentMode).",
    )
    parser.add_argument("--pair-id", help="Paired-run identity; sends logs to data/paired/.")
    parser.add_argument("--arm", help="Arm label within the pair, e.g. 'fixed'.")
    parser.add_argument(
        "--run-mode", choices=["time", "vehicles"],
        help="How the run ends (default: state.run_mode).",
    )
    parser.add_argument(
        "--count", type=int,
        help="Vehicle target for 'vehicles' mode (default: state.target_vehicle_count).",
    )
    parser.add_argument("--uneven-mode", help="Demand skew (default: state.uneven_mode).")
    parser.add_argument(
        "--duration", type=int,
        help="Run length in seconds for 'time' mode (default: state.duration).",
    )
    parser.add_argument(
        "--timeout", type=int,
        help="Safety cap in seconds for 'vehicles' mode "
             "(default: state.count_mode_timeout).",
    )
    return parser.parse_args(argv)


def apply_args(args):
    """Fold the given CLI overrides into state, then load the plan if any."""
    if args.controller is not None:
        state.currentMode = args.controller
    if args.run_mode is not None:
        state.run_mode = args.run_mode
    if args.count is not None:
        state.target_vehicle_count = args.count
    if args.uneven_mode is not None:
        state.uneven_mode = args.uneven_mode
    if args.duration is not None:
        state.duration = args.duration
    if args.timeout is not None:
        state.count_mode_timeout = args.timeout
    if args.pair_id is not None:
        state.pair_id = args.pair_id
    if args.arm is not None:
        state.arm_label = args.arm

    if args.plan is not None:
        load_plan_into_state(args.plan)

    if state.pair_id is not None:
        if state.generation_source != 'plan':
            # A paired run whose arms drew their own traffic is the unpaired
            # comparison this whole design exists to replace — and it would
            # look identical on disk.  Refuse it rather than produce data that
            # is wrong in a way nobody can see afterwards.
            print(
                "ERROR: --pair-id was given without --plan. A paired run must "
                "replay a plan, otherwise each arm faces different traffic and "
                "the comparison is not paired at all."
            )
            sys.exit(2)

        if state.pair_id != state.vehicle_plan['header']['plan_id']:
            print("ERROR: --pair-id must match the loaded plan's plan_id.")
            sys.exit(2)

        if state.arm_label is None:
            # The arm folder is what makes parts[-2] meaningful; default it to
            # the controller rather than writing into an unnamed folder.
            state.arm_label = state.currentMode


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
    state.generation_source = 'plan'
    state.vehicle_plan_path = path
    state.vehicle_plan = plan
    # The plan defines N; termination logic is otherwise untouched.
    state.run_mode = 'vehicles'
    state.target_vehicle_count = header['target_vehicle_count']
    state.uneven_mode = header['uneven_mode']


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


def shutdown(reason, elapsed, started_at, fps_stats=None):
    """
    Stop the background threads, record how the run ended, and exit.

    Everything written here runs on the main thread, before sys.exit: the
    shutdown path has no thread join and no flush barrier, so a sidecar field
    computed on the generator thread could simply never be written.
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
            # Frame rate is only recorded for paired runs.  An ordinary count
            # run's sidecar must keep exactly the keys it has always had —
            # comparing a plain 'vehicles' run before and after this feature
            # is the regression test, and extra keys would break it.
            **(fps_stats if state.pair_id is not None else {}),
        )
    else:
        print(f"Simulation ended ({reason}) after {elapsed:.1f}s")

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
        self._window_started_at = time.time()
        self._window_frames = 0
        self._fps_min = None

    def tick(self):
        self.frames_total += 1
        self._window_frames += 1

        elapsed = time.time() - self._window_started_at
        if elapsed >= FPS_SAMPLE_WINDOW_SEC:
            window_fps = self._window_frames / elapsed
            if self._fps_min is None or window_fps < self._fps_min:
                self._fps_min = window_fps
            self._window_started_at = time.time()
            self._window_frames = 0

    def stats(self, elapsed):
        return {
            "frames_total": self.frames_total,
            "fps_mean": round(self.frames_total / elapsed, 2) if elapsed else None,
            "fps_min": round(self._fps_min, 2) if self._fps_min is not None else None,
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

    if state.run_mode == 'vehicles':
        print(
            f"Run mode: vehicles | target = {state.target_vehicle_count} "
            f"| controller = {state.currentMode} | load = {state.uneven_mode} "
            f"| source = {state.generation_source} "
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
    fps = FpsTracker()

    while True:
        # Check whether the run is over
        elapsed_time = time.time() - start_time
        stop_reason = should_stop(elapsed_time)

        if stop_reason == 'target_reached':
            # Let in-flight turns finish before closing the window
            if target_reached_at is None:
                target_reached_at = time.time()
            elif time.time() - target_reached_at >= COUNT_MODE_DRAIN_SEC:
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

        # draw_buildings(screen)

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