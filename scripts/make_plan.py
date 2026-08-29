#!/usr/bin/env python3
"""
Write replay plans: the vehicle stream two controllers will each face.

A plan is generated on paper — a pure function of (seed, count, uneven_mode,
config), no pygame and no simulation — so producing fifty of them costs
milliseconds.  What a real dry run would capture instead is the sleep drift of
one machine on one day, which is not a property of the traffic and would be
re-imposed with *different* drift on both replays anyway.  What matters is
that both arms get the same intended schedule, and that each arm measures how
well it honoured it (see the drift fields in the run's _meta.json).

    python3 scripts/make_plan.py --seed 7 --count 500 --uneven-mode even
    python3 scripts/make_plan.py --plans 10 --count 500 --uneven-mode even
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.plan import build_plan, write_plan, default_plan_id  # noqa: E402

BASE_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)


def plan_path(plan_id, out=None):
    """Plans live beside the arm folders that will replay them."""
    if out is not None:
        return out
    return os.path.join(BASE_DATA_DIR, "paired", plan_id, "plan.json")


def make_one(seed, count, uneven_mode, out=None, plan_id=None):
    plan_id = plan_id or default_plan_id(uneven_mode, count, seed)
    plan = build_plan(seed, count, uneven_mode, plan_id=plan_id)
    path = write_plan(plan, plan_path(plan_id, out))

    last = plan['vehicles'][-1]['t_offset_sec']
    conditions = " -> ".join(
        f"{entry['condition']}@{entry['t_offset_sec']:.0f}s"
        for entry in plan['condition_timeline']
    )
    print(
        f"{plan_id}: {count} vehicles over {last:.0f}s of planned time "
        f"(hash {plan['header']['content_hash']})\n"
        f"  {conditions}\n"
        f"  -> {path}"
    )
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=0,
                        help="Seed for a single plan, or the first seed of a batch.")
    parser.add_argument("--count", type=int, default=500,
                        help="Number of vehicles in the plan.")
    parser.add_argument("--uneven-mode", default="even",
                        help="Demand skew the plan is drawn under.")
    parser.add_argument("--plans", type=int, default=1,
                        help="Emit this many plans, using consecutive seeds from --seed.")
    parser.add_argument("--plan-id",
                        help="Override the plan id (single-plan runs only).")
    parser.add_argument("--out",
                        help="Write to this exact path instead of "
                             "data/paired/{plan_id}/plan.json (single-plan runs only).")
    args = parser.parse_args(argv)

    if args.plans > 1 and (args.out or args.plan_id):
        parser.error("--out and --plan-id only apply when writing a single plan.")

    for offset in range(args.plans):
        make_one(
            seed=args.seed + offset,
            count=args.count,
            uneven_mode=args.uneven_mode,
            out=args.out,
            plan_id=args.plan_id,
        )


if __name__ == "__main__":
    main()
