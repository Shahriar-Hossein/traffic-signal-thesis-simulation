#!/usr/bin/env python3
"""
The frozen scenario grid, and the seeds reserved for evaluation.

Scenarios are defined here, once, before results are collected. The point is
that the grid cannot be quietly reshaped after seeing which cells favour the
proposed controller — so this file is meant to be read in a diff.

Two axes:

  skew    how demand is spread across the four approaches
  regime  how much demand is offered, in vehicles per second

The regimes are **offered arrival rates**, not capacity levels:

  low     0.5 veh/s
  medium  2   veh/s
  high    4   veh/s
  mixed   switching   all three in turn, the changing-demand case

These were previously labelled below / at / over capacity, on the grounds
that fixed-24 cleared 500 vehicles in 248 s on `even_500_seed201` — about 2.0
veh/s. That figure is `N / clearance_time` for one finite workload, which the
protocol elsewhere correctly says is not a capacity estimate: it averages
over the fill and drain of a queue that never reached a steady state, and one
balanced aggregate cannot certify capacity for an 85/5/5/5 allocation under
every controller anyway.

Establishing capacity needs sustained demand and a queue criterion, measured
per approach and per control policy. Until that is done these stay offered
rates, and whether a cell is saturated is a hypothesis recorded in the
protocol rather than a property of its name. The grid itself is unchanged.

Seeds are split so that tuning can never touch the evaluation set:

  DEVELOPMENT_SEEDS  free to inspect, tune against and rerun
  EVALUATION_SEEDS   reserved; run once, after the protocol is frozen

    python3 scripts/scenarios.py --list
    python3 scripts/scenarios.py --commands --arms fixed priority
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Balanced, moderately skewed, strongly skewed. The weights live in
# core/plan.py; these are the three levels the grid uses.
SKEWS = {
    'balanced': 'even',            # 0.25 each
    'moderate': 'right_down',      # 0.35 / 0.35 / 0.15 / 0.15
    'strong': 'right',             # 0.85 / 0.05 / 0.05 / 0.05
}

# Named for the rate offered, not for a capacity status that has not been
# measured. None means the plan switches conditions instead of holding one.
REGIMES = {
    'low': 'low',        # 0.5 veh/s
    'medium': 'medium',  # 2 veh/s
    'high': 'high',      # 4 veh/s
    'changing': None,
}

VEHICLE_COUNT = 500

DEVELOPMENT_SEEDS = (301, 302, 303, 304, 305, 306, 307, 308)

# Reserved. Do not run these until the protocol is frozen, and do not tune
# anything against them afterwards.
EVALUATION_SEEDS = tuple(range(9001, 9021))


def scenarios():
    """Every (skew, regime) cell of the grid, in a stable order."""
    for skew_name, uneven_mode in SKEWS.items():
        for regime_name, condition in REGIMES.items():
            yield {
                'scenario': f'{skew_name}_{regime_name}',
                'skew': skew_name,
                'regime': regime_name,
                'uneven_mode': uneven_mode,
                'condition': condition,
                'count': VEHICLE_COUNT,
            }


def commands(seeds, arms, timeout=3000):
    """The exact driver invocations this grid expands to."""
    lines = []
    for scenario in scenarios():
        for seed in seeds:
            condition = ''
            if scenario['condition'] is not None:
                condition = f" --condition {scenario['condition']}"
            lines.append(
                f"python3 run_paired.py --seed {seed} --count {scenario['count']}"
                f" --uneven-mode {scenario['uneven_mode']}{condition}"
                f" --arms {' '.join(arms)} --timeout {timeout}"
            )
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true', help='print the grid')
    group.add_argument('--commands', action='store_true', help='print run commands')
    parser.add_argument('--evaluation', action='store_true',
                        help='use the reserved evaluation seeds instead of development ones')
    parser.add_argument('--arms', nargs='+', default=['fixed', 'priority'])
    parser.add_argument('--timeout', type=int, default=3000)
    args = parser.parse_args(argv)

    if args.list:
        print(f"{'scenario':24} {'uneven_mode':14} {'condition':10} count")
        for scenario in scenarios():
            print(f"{scenario['scenario']:24} {scenario['uneven_mode']:14} "
                  f"{str(scenario['condition']):10} {scenario['count']}")
        print(f"\ndevelopment seeds: {list(DEVELOPMENT_SEEDS)}")
        print(f"evaluation seeds (reserved): {list(EVALUATION_SEEDS)}")
        return

    seeds = EVALUATION_SEEDS if args.evaluation else DEVELOPMENT_SEEDS
    for line in commands(seeds, args.arms, args.timeout):
        print(line)


if __name__ == '__main__':
    main()
