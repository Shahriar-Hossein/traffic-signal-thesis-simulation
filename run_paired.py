#!/usr/bin/env python3
"""
Run every arm of a paired replay against one plan, then compare them.

    python3 run_paired.py --plan data/paired/even_500_seed07/plan.json
    python3 run_paired.py --seed 7 --count 500 --arms fixed priority
    python3 run_paired.py --plans data/paired --arms fixed priority

The arms run **sequentially, one process at a time** — never the parallel
pattern in run_simulation.py.  Physics runs inside the renderer, so two pygame
processes competing for CPU and GPU do not get the same frame rate, and the
arm that renders slower has literally slower vehicles.  That confound is
indistinguishable from a controller effect, which would defeat the entire
point of pairing the traffic.

Arms are a list, not a pair: `--arms fixed priority fairness_priority` works,
and an arm may name its controller explicitly as `label=controller` when the
same controller is wanted twice (e.g. a `fixed_a=fixed` sanity arm).
"""

import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from analyzers.analyze_paired import (  # noqa: E402
    analyze_pair, analyze_batch, print_pair,
    DEFAULT_FPS_TOLERANCE, DEFAULT_DRIFT_TOLERANCE_MS,
)
from core.plan import build_plan, write_plan, default_plan_id  # noqa: E402
from scripts.make_plan import plan_path  # noqa: E402

PAIRED_ROOT = os.path.join(ROOT, "data", "paired")


def parse_arm(spec):
    """'priority' -> ('priority', 'priority');  'a=fixed' -> ('a', 'fixed')."""
    if "=" in spec:
        label, controller = spec.split("=", 1)
        return label, controller
    return spec, spec


def run_arm(plan_file, plan_id, label, controller, timeout=None):
    """
    Run one arm as its own process and report whether it is usable.

    One run per process is not a stylistic choice: the logger's filename is a
    module global set once, so two arms in one process would overwrite each
    other's identity.
    """
    cmd = [
        sys.executable, os.path.join(ROOT, "main.py"),
        "--plan", plan_file,
        "--controller", controller,
        "--pair-id", plan_id,
        "--arm", label,
    ]
    if timeout is not None:
        cmd += ["--timeout", str(timeout)]

    print(f"\n▶ arm '{label}' (controller={controller})")
    print("  " + " ".join(cmd))

    process = subprocess.Popen(cmd, cwd=ROOT)
    returncode = process.wait()

    if returncode != 0:
        return {"arm": label, "ok": False,
                "reason": f"exit code {returncode}"}

    meta = read_arm_meta(plan_id, label)
    if meta is None:
        return {"arm": label, "ok": False,
                "reason": "no _meta.json was written"}
    if meta.get("stop_reason") != "target_reached":
        return {"arm": label, "ok": False,
                "reason": f"stop_reason={meta.get('stop_reason')!r}"}

    return {"arm": label, "ok": True, "reason": None, "meta": meta}


def read_arm_meta(plan_id, label):
    arm_dir = os.path.join(PAIRED_ROOT, plan_id, label)
    if not os.path.isdir(arm_dir):
        return None
    metas = sorted(
        f for f in os.listdir(arm_dir) if f.endswith("_meta.json")
    )
    if not metas:
        return None
    with open(os.path.join(arm_dir, metas[-1])) as f:
        return json.load(f)


def run_pair(plan_file, arms, timeout=None, fps_tolerance=DEFAULT_FPS_TOLERANCE,
             drift_tolerance_ms=DEFAULT_DRIFT_TOLERANCE_MS):
    """Run every arm against one plan, then analyze and write comparison.json."""
    with open(plan_file) as f:
        header = json.load(f)["header"]
    plan_id = header["plan_id"]
    plan_dir = os.path.join(PAIRED_ROOT, plan_id)

    print(f"\n══ pair {plan_id}: {header['target_vehicle_count']} vehicles, "
          f"{len(arms)} arm(s), run one at a time ══")

    results = []
    for label, controller in arms:
        result = run_arm(plan_file, plan_id, label, controller, timeout)
        results.append(result)
        if not result["ok"]:
            print(f"  ✗ arm '{label}' failed: {result['reason']}")

    failed = [r for r in results if not r["ok"]]
    if failed:
        # One bad arm invalidates the pair — the surviving arm has nothing to
        # be paired against, and reporting it alone is the unpaired comparison
        # this design exists to replace.
        print(
            f"\n⛔ pair {plan_id} failed: "
            + "; ".join(f"{r['arm']}: {r['reason']}" for r in failed)
        )

    # The driver knows the order the user listed the arms in, so it names the
    # baseline explicitly rather than leaving the analyzer to infer it.
    comparison = analyze_pair(plan_dir, fps_tolerance, drift_tolerance_ms,
                              baseline=arms[0][0])
    if failed:
        comparison["valid"] = False
        comparison.setdefault("invalid_reasons", []).extend(
            f"{r['arm']}: {r['reason']}" for r in failed
        )
        from analyzers.analyze_paired import write_comparison
        write_comparison(plan_dir, comparison)

    print_pair(comparison)
    return comparison


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--plan", help="Replay an existing plan file.")
    source.add_argument("--seed", type=int, help="Generate a plan from this seed first.")
    source.add_argument("--plans", metavar="DIR",
                        help="Sweep every plan folder under DIR and aggregate.")

    parser.add_argument("--arms", nargs="+", default=["fixed", "priority"],
                        help="Arms to run, in order. 'label=controller' to name an arm.")
    parser.add_argument("--count", type=int, default=500,
                        help="Vehicles per plan (only with --seed).")
    parser.add_argument("--uneven-mode", default="even",
                        help="Demand skew for the generated plan (only with --seed).")
    parser.add_argument("--timeout", type=int,
                        help="Per-arm safety cap in seconds (default: state.py value).")
    parser.add_argument("--fps-tolerance", type=float, default=DEFAULT_FPS_TOLERANCE)
    parser.add_argument("--drift-tolerance-ms", type=float,
                        default=DEFAULT_DRIFT_TOLERANCE_MS)
    args = parser.parse_args(argv)

    arms = [parse_arm(spec) for spec in args.arms]
    labels = [label for label, _ in arms]
    if len(set(labels)) != len(labels):
        parser.error("arm labels must be unique — they name the log folders.")

    if args.plans:
        plan_files = sorted(
            os.path.join(args.plans, name, "plan.json")
            for name in os.listdir(args.plans)
            if os.path.exists(os.path.join(args.plans, name, "plan.json"))
        )
        if not plan_files:
            parser.error(f"no plan.json found under {args.plans}")

        for plan_file in plan_files:
            run_pair(plan_file, arms, args.timeout,
                     args.fps_tolerance, args.drift_tolerance_ms)

        aggregate = analyze_batch(args.plans, args.fps_tolerance,
                                  args.drift_tolerance_ms, baseline=arms[0][0])
        print(f"\n{aggregate['plans_valid']}/{aggregate['plans_total']} plans valid")
        for key, block in aggregate["per_contrast"].items():
            p = block["wilcoxon_p_value"]
            print(
                f"  {key}: Δwait mean of plan means "
                f"{block['delta_wait_mean_of_plan_means']} over "
                f"{block['plans']} plans, "
                f"p={'n/a' if p is None else f'{p:.2e}'}"
            )
        return

    if args.seed is not None:
        plan_id = default_plan_id(args.uneven_mode, args.count, args.seed)
        plan = build_plan(args.seed, args.count, args.uneven_mode, plan_id=plan_id)
        plan_file = write_plan(plan, plan_path(plan_id))
        print(f"Wrote plan {plan_id} -> {plan_file}")
    else:
        plan_file = args.plan

    comparison = run_pair(plan_file, arms, args.timeout,
                          args.fps_tolerance, args.drift_tolerance_ms)
    sys.exit(0 if comparison.get("valid") else 1)


if __name__ == "__main__":
    main()
