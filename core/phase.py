# core/phase.py
"""
One signal phase, executed the same way by every controller.

Fixed, priority, fairness and the two ablations each used to carry their own
copy of the transition: expose the green, count it down, run the yellow, write
the record, reset the timers.  Four copies meant the same two defects existed
in four places, and a fix to one was not a fix to the others.

What the policies still own — and all they own — is the *decision*: which
approach is served next, how long its green is, and whether it may end early.
Everything below is mechanism.

Two properties this file is responsible for:

  * A phase is recorded from the moment it is decided (`begin_phase`), not
    when it finishes.  A run that ends mid-phase still has that phase in its
    log, marked censored.
  * Movement permission and the phase record describe the same transition.
    Green is withdrawn before the record is written, so the approach that has
    just finished is not green again during a blocking disk write.
"""
import time

import state
from config import (
    defaultGreen, defaultRed, defaultStop, defaultYellow,
    directionNumbers, noOfSignals,
)
from core import runclock
from core.updater import update_signal_timers
from models.traffic_signal import signals
from utils.counters import get_vehicle_counts, get_weighted_vehicle_counts
from utils.logger import (
    begin_phase, complete_phase, log_signal_change, mark_green_end,
)

ALL_RED_SEC = 10

# No approach is green.  The warm-up already used this value, so the renderer
# and `Vehicle.move` have always handled it.
NO_GREEN = -1

FIXED_ORDER = [0, 1, 2, 3]  # right, down, left, up


def all_red_start():
    """The warm-up every controller begins with: all red, accumulating queues."""
    for signal in signals:
        signal.red = ALL_RED_SEC
        signal.green = 0
        signal.yellow = 0

    state.currentGreen = NO_GREEN
    state.currentYellow = 0

    print(f"Initial all-red phase for {ALL_RED_SEC} seconds to accumulate vehicles.")
    for _ in range(ALL_RED_SEC):
        for i in range(noOfSignals):
            signals[i].red = max(0, signals[i].red - 1)
        time.sleep(1)


def decide(green_index):
    """
    Snapshot the counts one decision is made from.

    Taken once and passed to `run_phase`, so the weight recorded in the phase
    log is the same number the green duration was computed from.  Measuring
    again inside the phase would log a different snapshot than the one that
    decided.
    """
    weights = get_weighted_vehicle_counts()
    return weights, get_vehicle_counts(), weights[directionNumbers[green_index]]


def rank_by_demand(indices, weights):
    """The approaches in `indices`, most-demanded first."""
    return sorted(indices, key=lambda idx: weights[directionNumbers[idx]],
                  reverse=True)


def run_phase(green_index, green_time, round_index, phase_index, weights,
              queues, red_extra=1, early_exit=None):
    """
    Serve one green-then-yellow phase for `green_index` and record it.

    `red_extra` is the extra second the demand-sized controllers add to the
    red they set on the served approach; fixed does not add it.  It is carried
    as a parameter rather than unified so this refactor does not silently
    change any controller's signal timing.

    `early_exit(direction, second)` is consulted once per green second before
    that second elapses; returning True ends the green there and records the
    phase as terminating early rather than on duration.
    """
    direction = directionNumbers[green_index]

    # The decision is captured before the green it authorises is exposed.
    green_start = runclock.elapsed()
    begin_phase(
        round_index=round_index, phase_index=phase_index, direction=direction,
        green_start_sec=green_start, green_selected_sec=green_time,
        decision_weight=weights[direction],
        decision_counts=weights, queue_counts=queues,
    )
    log_signal_change(direction)

    signals[green_index].green = green_time
    signals[green_index].yellow = defaultYellow
    signals[green_index].red = green_time + defaultYellow + red_extra

    state.currentYellow = 0
    state.currentGreen = green_index

    termination = 'duration'
    for second in range(green_time):
        if early_exit is not None and early_exit(direction, second):
            termination = 'early_exit'
            break
        update_signal_timers(green_index, yellow=False)
        time.sleep(1)

    green_end = runclock.elapsed()
    mark_green_end(green_end, termination)

    state.currentYellow = 1
    for lane in range(3):
        for vehicle in state.vehicles[direction][lane]:
            vehicle.stop = defaultStop[direction]
    for _ in range(defaultYellow):
        update_signal_timers(green_index, yellow=True)
        time.sleep(1)

    # End the phase atomically.  `Vehicle.move` reads currentGreen and
    # currentYellow together, so clearing the yellow first would hand this
    # approach an unrecorded extra green for as long as the record below takes
    # to write.  Withdrawing the green first makes that window all-red — the
    # state the intersection is actually in between phases.  No sleep is added
    # here: the intended phasing is unchanged.
    state.currentGreen = NO_GREEN
    state.currentYellow = 0
    complete_phase(runclock.elapsed())

    signals[green_index].green = defaultGreen[green_index]
    signals[green_index].yellow = defaultYellow
    signals[green_index].red = defaultRed
