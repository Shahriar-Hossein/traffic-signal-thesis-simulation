# core/cycle_ablation.py
"""
Ablation controllers that split the proposed rule into its two parts.

Against fixed-24 the proposed controller changes two things at once: which
approach is served next, and how long its green lasts. Each arm here changes
exactly one of them, so an observed effect can be attributed to ordering or to
duration rather than to their combination.

    fixed_order_adaptive_duration  fixed rotation, demand-sized green
    adaptive_order_fixed_duration  demand-ordered rotation, 24-second green

cycle_priority is deliberately not imported or modified — the proposed
controller must keep running exactly the code it was validated with. The
duration rule is restated here and pinned to that original by a test.
"""
from models.traffic_signal import signals
import state
import time
from config import (
    defaultRed, defaultYellow, defaultGreen,
    directionNumbers, noOfSignals, defaultStop
)
from core import runclock
from core.updater import update_signal_timers
from utils.counters import get_vehicle_counts, get_weighted_vehicle_counts
from utils.logger import log_signal_change, log_phase

FIXED_ORDER = [0, 1, 2, 3]  # right, down, left, up
ALL_RED_SEC = 10


def adaptive_green(weight):
    """
    The proposed controller's duration rule, restated.

    Kept identical to the expression inline in cycle_priority; a test compares
    the two over a range of weights so they cannot drift apart unnoticed.
    """
    return max(6, min(int(weight * 0.75), 24))


def all_red_start():
    """The same warm-up every controller here begins with."""
    for signal in signals:
        signal.red = ALL_RED_SEC
        signal.green = 0
        signal.yellow = 0

    state.currentGreen = -1
    state.currentYellow = 0

    print(f"Initial all-red phase for {ALL_RED_SEC} seconds to accumulate vehicles.")
    for _ in range(ALL_RED_SEC):
        for i in range(noOfSignals):
            signals[i].red = max(0, signals[i].red - 1)
        time.sleep(1)


def decide(green_index):
    """
    Snapshot the counts one decision is made from.

    Taken once and passed to `serve`, so the weight recorded in the phase log
    is the same number the green duration was computed from. Measuring again
    inside `serve` would log a different snapshot than the one that decided.
    """
    weights = get_weighted_vehicle_counts()
    return weights, get_vehicle_counts(), weights[directionNumbers[green_index]]


def serve(green_index, green_time, round_index, phase_index, weights, queues):
    """
    Run one green-then-yellow phase and record it.

    Mechanically identical to the phase both existing controllers run, so the
    arms differ only in the order they serve and the duration they choose.
    """
    state.currentGreen = green_index
    direction = directionNumbers[green_index]
    log_signal_change(direction)

    green_start = runclock.elapsed()

    signals[green_index].green = green_time
    signals[green_index].yellow = defaultYellow
    signals[green_index].red = green_time + defaultYellow + 1
    for _ in range(green_time):
        update_signal_timers(green_index, yellow=False)
        time.sleep(1)

    green_end = runclock.elapsed()

    state.currentYellow = 1
    for lane in range(3):
        for vehicle in state.vehicles[direction][lane]:
            vehicle.stop = defaultStop[direction]
    for _ in range(defaultYellow):
        update_signal_timers(green_index, yellow=True)
        time.sleep(1)
    state.currentYellow = 0

    log_phase(
        round_index=round_index, phase_index=phase_index, direction=direction,
        green_start_sec=green_start, green_selected_sec=green_time,
        green_end_sec=green_end, phase_end_sec=runclock.elapsed(),
        decision_weight=weights[direction],
        decision_counts=weights, queue_counts=queues,
    )

    signals[green_index].green = defaultGreen[green_index]
    signals[green_index].yellow = defaultYellow
    signals[green_index].red = defaultRed


def fixed_order_adaptive_duration_cycle():
    """Fixed rotation; green sized by the proposed duration rule."""
    all_red_start()

    round_index = 0
    while state.running:
        for phase_index, green_index in enumerate(FIXED_ORDER):
            weights, queues, weight = decide(green_index)
            serve(green_index, adaptive_green(weight), round_index, phase_index,
                  weights, queues)
        round_index += 1


def adaptive_order_fixed_duration_cycle():
    """
    Demand-ordered rotation; every green is the fixed baseline's 24 seconds.

    The ordering logic mirrors the proposed controller: rank the four
    approaches, serve the largest, then recount and reorder only those still
    unserved this round.
    """
    all_red_start()

    round_index = 0
    while state.running:
        weights = get_weighted_vehicle_counts()
        order = sorted(FIXED_ORDER, key=lambda idx: weights[directionNumbers[idx]],
                       reverse=True)

        phase_index = 0
        while order:
            green_index = order.pop(0)
            weights, queues, _ = decide(green_index)
            serve(green_index, defaultGreen[green_index], round_index, phase_index,
                  weights, queues)
            phase_index += 1

            if order:
                weights = get_weighted_vehicle_counts()
                order = sorted(order, key=lambda idx: weights[directionNumbers[idx]],
                               reverse=True)
        round_index += 1
