#!/usr/bin/env python3
"""
Prove that the extracted sampler draws exactly what the old inline code drew.

Before the paired-replay work, the type/direction/lane draws lived inline in
`generateVehicles` and the turn draws lived inline in `Vehicle.__init__`.
Both moved into `core.plan.sample_vehicle` / `sample_turn` so the plan writer
and the live generator cannot drift apart.

That extraction was the one moment a before/after equivalence test was
possible, so the pre-change logic is pinned below verbatim.  Re-run this after
touching either sampler: if the draw *order* changes, seeded reproduction of
the old sequence breaks and this is the only thing that would notice.

    python3 scripts/verify_sampler_equivalence.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import directionNumbers, vehicleTypes, turnDirections, turnProbability  # noqa: E402
from core.plan import sample_vehicle, sample_turn  # noqa: E402

DRAWS_PER_MODE = 1000
SEEDS = (1, 7, 42)
MODES = (None, 'even', 'up', 'down', 'left', 'right', 'up_down', 'left_right',
         'down_left', 'right_down', 'right_up', 'left_up')


def old_inline(uneven_mode, n):
    """The pre-extraction draw sequence, copied verbatim. Do not tidy this up."""
    out = []
    for _ in range(n):
        vehicle_type_index = random.randint(0, 3)

        if uneven_mode == 'down_left':
            directions = ['right', 'down', 'left', 'up']; weights = [0.15, 0.35, 0.35, 0.15]
        elif uneven_mode == 'right_down':
            directions = ['right', 'down', 'left', 'up']; weights = [0.35, 0.35, 0.15, 0.15]
        elif uneven_mode == 'right_up':
            directions = ['right', 'down', 'left', 'up']; weights = [0.35, 0.15, 0.15, 0.35]
        elif uneven_mode == 'left_up':
            directions = ['right', 'down', 'left', 'up']; weights = [0.15, 0.15, 0.35, 0.35]
        elif uneven_mode == 'up':
            directions = ['right', 'down', 'left', 'up']; weights = [0.05, 0.05, 0.05, 0.85]
        elif uneven_mode == 'down':
            directions = ['right', 'down', 'left', 'up']; weights = [0.05, 0.85, 0.05, 0.05]
        elif uneven_mode == 'left':
            directions = ['right', 'down', 'left', 'up']; weights = [0.05, 0.05, 0.85, 0.05]
        elif uneven_mode == 'right':
            directions = ['right', 'down', 'left', 'up']; weights = [0.85, 0.05, 0.05, 0.05]
        elif uneven_mode == 'up_down':
            directions = ['right', 'down', 'left', 'up']; weights = [0.15, 0.35, 0.15, 0.35]
        elif uneven_mode == 'left_right':
            directions = ['right', 'down', 'left', 'up']; weights = [0.35, 0.15, 0.35, 0.15]
        else:
            directions = ['right', 'down', 'left', 'up']; weights = [0.25, 0.25, 0.25, 0.25]

        direction = random.choices(directions, weights)[0]
        direction_number = list(directionNumbers.values()).index(direction)
        lane_number = random.randint(0, 2)

        # ...and the turn draws, which used to live in Vehicle.__init__
        possible_turn = turnDirections[direction][lane_number]
        if possible_turn != direction and random.random() < turnProbability:
            turn_direction, will_turn = possible_turn, True
            target_turn_lane = random.randint(0, 2)
        else:
            turn_direction, will_turn, target_turn_lane = direction, False, 0

        out.append((vehicleTypes[vehicle_type_index], direction, direction_number,
                    lane_number, will_turn, turn_direction, target_turn_lane))
    return out


def new_extracted(uneven_mode, n):
    out = []
    for _ in range(n):
        drawn = sample_vehicle(uneven_mode, random)
        turn = sample_turn(drawn['direction'], drawn['lane'], random)
        out.append((drawn['vehicle_type'], drawn['direction'], drawn['direction_number'],
                    drawn['lane'], turn['will_turn'], turn['turn_direction'],
                    turn['target_turn_lane']))
    return out


def main():
    failures = 0
    for mode in MODES:
        for seed in SEEDS:
            random.seed(seed)
            old = old_inline(mode, DRAWS_PER_MODE)
            random.seed(seed)
            new = new_extracted(mode, DRAWS_PER_MODE)

            if old == new:
                print(f"ok   mode={str(mode):11} seed={seed:<3} "
                      f"{DRAWS_PER_MODE} draws identical")
            else:
                failures += 1
                index = next(i for i, (a, b) in enumerate(zip(old, new)) if a != b)
                print(f"FAIL mode={str(mode):11} seed={seed:<3} "
                      f"first difference at draw {index}:\n"
                      f"       old: {old[index]}\n       new: {new[index]}")

    if failures:
        print(f"\n❌ {failures} mode/seed combination(s) diverged.")
        return 1

    print("\n✅ The extracted sampler is draw-for-draw identical to the old inline code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
