#!/usr/bin/env python3
"""Write independent, duration-based plans for the small paired study."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.plan import build_plan, write_plan  # noqa: E402

SCENARIOS = {
    'balanced_moderate': ('even', [('medium', 120)]),
    'one_busy': ('right', [('medium', 120)]),
    'two_busy': ('up_down', [('medium', 120)]),
    'high_low_high': ('even', [('high', 45), ('low', 45), ('high', 45)]),
    'sustained_high': ('even', [('high', 120)]),
}
DEVELOPMENT_SEEDS = (301, 302, 303, 304, 305)


def make_plans(root, scenarios=SCENARIOS, seeds=DEVELOPMENT_SEEDS):
    """Refuse overwrites so a plan archive remains tied to its first hash."""
    root = Path(root)
    destinations = [root / f'{name}_seed{seed}' / 'plan.json'
                    for name in scenarios for seed in seeds]
    if len(set(destinations)) != len(destinations):
        raise ValueError('scenario/seed selection contains duplicate plan IDs')
    existing = [path for path in destinations if path.exists()]
    if existing:
        raise FileExistsError(f'plan already exists: {existing[0]}')
    written = []
    for name, (mode, periods) in scenarios.items():
        schedule = [{'condition': condition, 'duration_sec': seconds}
                    for condition, seconds in periods]
        for seed in seeds:
            plan_id = f'{name}_seed{seed}'
            path = root / plan_id / 'plan.json'
            plan = build_plan(seed, None, mode, plan_id=plan_id,
                              schedule=schedule, scenario=name)
            write_plan(plan, str(path))
            written.append(path)
            print(f'{plan_id}: {len(plan["vehicles"])} arrivals, '
                  f'hash {plan["header"]["content_hash"]}')
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', default='data/study')
    parser.add_argument('--scenario', choices=SCENARIOS,
                        help='One environment; default is all five.')
    parser.add_argument('--seeds', nargs='+', type=int,
                        default=DEVELOPMENT_SEEDS)
    args = parser.parse_args(argv)
    scenarios = {args.scenario: SCENARIOS[args.scenario]} if args.scenario else SCENARIOS
    make_plans(args.output_root, scenarios, args.seeds)


if __name__ == '__main__':
    main()
