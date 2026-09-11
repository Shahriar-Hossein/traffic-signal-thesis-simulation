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
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from analyzers.analyze_timing import analyze_timing, print_report  # noqa: E402
from analyzers.analyze_paired import (  # noqa: E402
    analyze_pair, analyze_batch, print_pair,
    DEFAULT_FPS_TOLERANCE, DEFAULT_DRIFT_TOLERANCE_MS,
)
from config import trafficConditions as TRAFFIC_CONDITIONS  # noqa: E402
from core.controllers import NAMES as CONTROLLER_NAMES  # noqa: E402
from core.fixed_timing import load_fixed_timing, resolve_fixed_greens  # noqa: E402
from core.plan import build_plan, write_plan, default_plan_id, load_plan  # noqa: E402

PAIRED_ROOT = os.path.join(ROOT, "data", "paired")


def parse_arm(spec):
    """'priority' -> ('priority', 'priority');  'a=fixed' -> ('a', 'fixed')."""
    if "=" in spec:
        label, controller = spec.split("=", 1)
        return label, controller
    return spec, spec


def run_arm(plan_file, plan_id, label, controller, timeout=None, paired_root=None,
            fixed_timing_plan=None):
    """
    Run one arm as its own process and report whether it is usable.

    One run per process is not a stylistic choice: the logger's filename is a
    module global set once, so two arms in one process would overwrite each
    other's identity.
    """
    paired_root = os.path.abspath(paired_root or PAIRED_ROOT)
    cmd = [
        sys.executable, os.path.join(ROOT, "main.py"),
        "--plan", plan_file,
        "--controller", controller,
        "--pair-id", plan_id,
        "--arm", label,
        "--paired-root", paired_root,
    ]
    if timeout is not None:
        cmd += ["--timeout", str(timeout)]
    if fixed_timing_plan is not None:
        cmd += ["--fixed-timing-plan", os.path.abspath(fixed_timing_plan)]

    print(f"\n▶ arm '{label}' (controller={controller})")
    print("  " + " ".join(cmd))

    process = subprocess.Popen(cmd, cwd=ROOT)
    returncode = process.wait()

    if returncode != 0:
        return {"arm": label, "ok": False,
                "reason": f"exit code {returncode}"}

    meta = read_arm_meta(plan_id, label, paired_root)
    if meta is None:
        return {"arm": label, "ok": False,
                "reason": "no _meta.json was written"}
    if meta.get("stop_reason") != "target_reached":
        return {"arm": label, "ok": False,
                "reason": f"stop_reason={meta.get('stop_reason')!r}"}

    return {"arm": label, "ok": True, "reason": None, "meta": meta}


def read_arm_meta(plan_id, label, paired_root=None):
    arm_dir = os.path.join(os.path.abspath(paired_root or PAIRED_ROOT), plan_id, label)
    if not os.path.isdir(arm_dir):
        return None
    metas = sorted(
        f for f in os.listdir(arm_dir) if f.endswith("_meta.json")
    )
    if not metas:
        return None
    try:
        with open(os.path.join(arm_dir, metas[-1])) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return None
    return meta if isinstance(meta, dict) else None


def preflight_pair(plan_file, arms, output_root=None, fixed_timing_plan=None):
    """Validate a pair destination without creating folders or running arms."""
    output_root = os.path.abspath(output_root or PAIRED_ROOT)
    plan = load_plan(plan_file)
    header = plan['header']
    plan_id = header['plan_id']
    if os.path.basename(plan_id) != plan_id or plan_id in ('.', '..'):
        raise ValueError('plan_id must be a single folder name')
    plan_dir = os.path.join(output_root, plan_id)
    for label, controller in arms:
        if os.path.basename(label) != label or label in ('', '.', '..'):
            raise ValueError('arm labels must be single folder names')
        if controller not in CONTROLLER_NAMES:
            raise ValueError(f'unknown controller: {controller}')
        folder = os.path.join(plan_dir, label)
        if os.path.exists(folder):
            raise ValueError(f'arm folder already exists: {folder}; use a fresh plan ID or arm label')
    timing_table = None
    if fixed_timing_plan is not None:
        timing_table = load_fixed_timing(fixed_timing_plan)
    if any(controller == 'fixed_tuned' for _, controller in arms):
        if timing_table is None:
            raise ValueError('fixed_tuned requires --fixed-timing-plan')
        resolve_fixed_greens(timing_table, header)
    archived_plan = os.path.join(plan_dir, 'plan.json')
    if os.path.exists(archived_plan):
        if load_plan(archived_plan)['header']['content_hash'] != header['content_hash']:
            raise ValueError('archived plan differs from requested plan')
    return {
        'plan': plan, 'plan_id': plan_id, 'plan_dir': plan_dir,
        'archived_plan': archived_plan, 'output_root': output_root,
    }


def write_driver_failure(plan_dir, header, arms, failed):
    """Persist a plan-bound failure so later reanalysis reaches the same verdict."""
    path = os.path.join(plan_dir, 'driver_status.json')
    status = {
        'schema_version': 1,
        'plan_id': header['plan_id'],
        'plan_hash': header['content_hash'],
        'expected_arms': [
            {'label': label, 'controller': controller}
            for label, controller in arms
        ],
        'failures': [
            {'arm': result['arm'], 'reason': result['reason']}
            for result in failed
        ],
    }
    with open(path, 'w') as handle:
        json.dump(status, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return path


def invalidate_failed_comparison(comparison, failed):
    """Remove every derived effect when orchestration says an arm failed."""
    reasons = [f"driver: {result['arm']}: {result['reason']}" for result in failed]
    comparison['measurement_valid'] = False
    comparison['publication_eligible'] = False
    comparison['valid'] = False
    comparison.setdefault('invalid_reasons', [])
    for reason in reasons:
        if reason not in comparison['invalid_reasons']:
            comparison['invalid_reasons'].append(reason)
    comparison['arms'] = {}
    comparison['baseline_arm'] = None
    comparison['paired'] = []
    return comparison


def run_pair(plan_file, arms, timeout=None, fps_tolerance=DEFAULT_FPS_TOLERANCE,
             drift_tolerance_ms=DEFAULT_DRIFT_TOLERANCE_MS, output_root=None,
             fixed_timing_plan=None):
    """Run every arm against one plan, then analyze and write comparison.json."""
    setup = preflight_pair(plan_file, arms, output_root, fixed_timing_plan)
    plan = setup['plan']
    header = plan['header']
    plan_id = setup['plan_id']
    plan_dir = setup['plan_dir']
    archived_plan = setup['archived_plan']
    output_root = setup['output_root']
    if not os.path.exists(archived_plan):
        os.makedirs(plan_dir, exist_ok=True)
        shutil.copyfile(plan_file, archived_plan)
    plan_file = archived_plan

    print(f"\n══ pair {plan_id}: {header['target_vehicle_count']} vehicles, "
          f"{len(arms)} arm(s), run one at a time ══")

    results = []
    for label, controller in arms:
        result = run_arm(
            plan_file, plan_id, label, controller, timeout, output_root,
            fixed_timing_plan,
        )
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
        write_driver_failure(plan_dir, header, arms, failed)

    # The driver knows the order the user listed the arms in, so it names the
    # baseline explicitly rather than leaving the analyzer to infer it.
    comparison = analyze_pair(plan_dir, fps_tolerance, drift_tolerance_ms,
                              baseline=arms[0][0])
    if failed:
        invalidate_failed_comparison(comparison, failed)
        from analyzers.analyze_paired import write_comparison
        write_comparison(plan_dir, comparison)

    print_pair(comparison)
    # Timing is reported for every pair, valid or not: when a pair is
    # rejected, the clocks are usually where the reason is.
    print_report(analyze_timing(
        plan_dir, baseline=arms[0][0], fps_tolerance=fps_tolerance
    ))
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
    parser.add_argument("--condition", choices=sorted(TRAFFIC_CONDITIONS),
                        help="Hold one demand regime for the generated plan "
                             "(only with --seed).")
    parser.add_argument("--timeout", type=int,
                        help="Per-arm safety cap in seconds (default: state.py value).")
    parser.add_argument("--fps-tolerance", type=float, default=DEFAULT_FPS_TOLERANCE)
    parser.add_argument("--drift-tolerance-ms", type=float,
                        default=DEFAULT_DRIFT_TOLERANCE_MS)
    parser.add_argument(
        "--output-root",
        help="Destination root for paired plans and logs (default: data/paired; "
             "with --plans, defaults to DIR).",
    )
    parser.add_argument(
        "--fixed-timing-plan",
        help="Validated scenario timing table required by fixed_tuned.",
    )
    args = parser.parse_args(argv)

    arms = [parse_arm(spec) for spec in args.arms]
    labels = [label for label, _ in arms]
    if len(set(labels)) != len(labels):
        parser.error("arm labels must be unique — they name the log folders.")

    if args.plans:
        output_root = os.path.abspath(args.output_root or args.plans)
        plan_files = sorted(
            os.path.join(args.plans, name, "plan.json")
            for name in os.listdir(args.plans)
            if os.path.exists(os.path.join(args.plans, name, "plan.json"))
        )
        if not plan_files:
            parser.error(f"no plan.json found under {args.plans}")

        # Resolve every plan and destination before the first long-running
        # simulation. Otherwise plan N can finish before plan N+1 discovers
        # that its arm folder already exists.
        preflight = [
            preflight_pair(path, arms, output_root, args.fixed_timing_plan)
            for path in plan_files
        ]
        plan_ids = [item['plan_id'] for item in preflight]
        if len(set(plan_ids)) != len(plan_ids):
            raise ValueError("selected plans contain duplicate plan IDs")

        comparisons = []
        for plan_file in plan_files:
            comparisons.append(run_pair(
                plan_file, arms, args.timeout,
                args.fps_tolerance, args.drift_tolerance_ms, output_root,
                args.fixed_timing_plan,
            ))

        aggregate = analyze_batch(
            output_root, args.fps_tolerance, args.drift_tolerance_ms,
            baseline=arms[0][0], plan_ids=plan_ids,
        )
        print(f"\n{aggregate['plans_valid']}/{aggregate['plans_total']} plans valid")
        for key, block in aggregate["per_contrast"].items():
            p = block["wilcoxon_p_value"]
            print(
                f"  {key}: Δwait mean of plan means "
                f"{block['delta_wait_mean_of_plan_means']} over "
                f"{block['plans']} plans, "
                f"p={'n/a' if p is None else f'{p:.2e}'}"
            )
        failed = (
            any(not item.get('publication_eligible', item.get('valid'))
                for item in comparisons)
            or bool(aggregate['plans_invalid'])
            or bool(aggregate['cohort_errors'])
            or bool(aggregate['duplicate_plans'])
        )
        return 1 if failed else 0

    if args.seed is not None:
        output_root = os.path.abspath(args.output_root or PAIRED_ROOT)
        plan_id = default_plan_id(args.uneven_mode, args.count, args.seed, args.condition)
        plan = build_plan(args.seed, args.count, args.uneven_mode, plan_id=plan_id,
                          condition=args.condition)
        plan_file = os.path.join(output_root, plan_id, 'plan.json')
        if os.path.exists(plan_file):
            parser.error(f'plan already exists: {plan_file}; use --plan or a fresh seed')
        write_plan(plan, plan_file)
        print(f"Wrote plan {plan_id} -> {plan_file}")
    else:
        plan_file = args.plan
        output_root = os.path.abspath(args.output_root or PAIRED_ROOT)

    comparison = run_pair(plan_file, arms, args.timeout,
                          args.fps_tolerance, args.drift_tolerance_ms,
                          output_root, args.fixed_timing_plan)
    return 0 if comparison.get(
        "publication_eligible", comparison.get("valid")
    ) else 1


if __name__ == "__main__":
    sys.exit(main())
