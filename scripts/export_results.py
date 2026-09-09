"""
Export a self-contained results package outside the ignored `data/` tree.

`data/*` is gitignored, so anything that lives only there cannot be cited,
reviewed or reproduced from the repository. This copies the plans, raw logs
and derived analyses into `results/<name>/` together with the code revision
and the exact commands that produced them.

    python3 scripts/export_results.py --name pilot_2026_09_10 \\
        data/paired/even_500_seed301 data/paired/even_500_seed302

Refuses to export from a dirty working tree unless --allow-dirty is given: a
package whose revision does not describe its own code is not reproducible.
"""
import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from analyzers.analyze_paired import analyze_pair  # noqa: E402
from analyzers.analyze_timing import analyze_timing  # noqa: E402
from analyzers.analyze_discharge import analyze_discharge  # noqa: E402

RESULTS_ROOT = os.path.join(ROOT, 'results')


def git(*args):
    try:
        return subprocess.run(['git', '-C', ROOT, *args], capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def revision():
    dirty = git('status', '--porcelain')
    return {
        'commit': git('rev-parse', 'HEAD'),
        'branch': git('rev-parse', '--abbrev-ref', 'HEAD'),
        'dirty': bool(dirty),
        'uncommitted': dirty.splitlines() if dirty else [],
    }


def arm_dirs(plan_dir):
    return sorted(
        os.path.join(plan_dir, name) for name in os.listdir(plan_dir)
        if os.path.isdir(os.path.join(plan_dir, name))
    )


def export_plan(plan_dir, destination):
    """Copy one plan folder's inputs and outputs, and derive its analyses."""
    name = os.path.basename(plan_dir.rstrip(os.sep))
    target = os.path.join(destination, name)
    os.makedirs(target, exist_ok=True)

    plan_file = os.path.join(plan_dir, 'plan.json')
    if os.path.exists(plan_file):
        shutil.copy2(plan_file, os.path.join(target, 'plan.json'))

    for arm_dir in arm_dirs(plan_dir):
        arm_target = os.path.join(target, os.path.basename(arm_dir))
        os.makedirs(arm_target, exist_ok=True)
        for entry in sorted(os.listdir(arm_dir)):
            source = os.path.join(arm_dir, entry)
            if os.path.isfile(source):
                shutil.copy2(source, os.path.join(arm_target, entry))

    comparison = analyze_pair(plan_dir, write=False)
    timing = analyze_timing(plan_dir, write=False)
    discharge = [analyze_discharge(arm_dir) for arm_dir in arm_dirs(plan_dir)]
    for filename, payload in (('comparison.json', comparison),
                              ('timing.json', timing),
                              ('discharge.json', discharge)):
        with open(os.path.join(target, filename), 'w') as handle:
            json.dump(payload, handle, indent=2)

    return {'plan_id': name, 'comparison': comparison,
            'timing': timing, 'discharge': discharge}


def summary_lines(exports):
    """A readable table, so the package is legible without running anything."""
    lines = ['# Results package', '',
             '| plan | arm | valid | vehicles | clearance s | wait mean | wait p95 | worst approach |',
             '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for export in exports:
        comparison = export['comparison']
        valid = 'yes' if comparison.get('valid') else 'NO'
        for arm, summary in comparison.get('arms', {}).items():
            lines.append(
                f"| {export['plan_id']} | {arm} | {valid} | "
                f"{summary['vehicles_logged']} | {summary['last_crossing_sec']} | "
                f"{summary['wait_mean']} | {summary['wait_p95']} | "
                f"{summary['worst_direction']} {summary['worst_direction_wait_mean']} |"
            )
        if not comparison.get('valid'):
            for reason in comparison.get('invalid_reasons', []):
                lines.append(f"| {export['plan_id']} | — | NO | | | | | {reason} |")

    lines += ['', '## Paired effects (one row per contrast, per plan)', '',
              '| plan | baseline | arm | n | delta wait mean | delta wait median | win rate |',
              '| --- | --- | --- | --- | --- | --- | --- |']
    for export in exports:
        for block in export['comparison'].get('paired', []):
            win_rate = block.get('win_rate_' + block['arm'])
            lines.append(
                f"| {export['plan_id']} | {block['baseline']} | {block['arm']} | "
                f"{block['n_matched']} | {block['delta_wait_mean']} | "
                f"{block['delta_wait_median']} | {win_rate} |"
            )
    return lines


def export(plan_dirs, name, allow_dirty=False):
    info = revision()
    if info['dirty'] and not allow_dirty:
        raise SystemExit(
            'refusing to export from a dirty working tree; commit first '
            'or pass --allow-dirty'
        )

    destination = os.path.join(RESULTS_ROOT, name)
    if os.path.exists(destination):
        raise SystemExit(f'{destination} already exists; choose another --name')
    os.makedirs(destination)

    exports = [export_plan(os.path.abspath(d), destination) for d in plan_dirs]

    manifest = {
        'name': name,
        'exported_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'revision': info,
        'python': platform.python_version(),
        'platform': platform.platform(),
        'plans': [export['plan_id'] for export in exports],
        'commands': {
            'export': f"python3 scripts/export_results.py --name {name} "
                      + ' '.join(plan_dirs),
            'pair': 'python3 analyzers/analyze_paired.py <plan_dir>',
            'batch': 'python3 analyzers/analyze_paired.py --batch data/paired',
            'timing': 'python3 analyzers/analyze_timing.py <plan_dir>',
            'discharge': 'python3 analyzers/analyze_discharge.py <arm_dir>',
        },
    }
    with open(os.path.join(destination, 'manifest.json'), 'w') as handle:
        json.dump(manifest, handle, indent=2)
    with open(os.path.join(destination, 'SUMMARY.md'), 'w') as handle:
        handle.write('\n'.join(summary_lines(exports)) + '\n')

    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan_dir', nargs='+', help='data/paired/{plan_id} folders')
    parser.add_argument('--name', required=True, help='package name under results/')
    parser.add_argument('--allow-dirty', action='store_true',
                        help='export even though the working tree has changes')
    args = parser.parse_args(argv)
    print(f"✅ Exported to {export(args.plan_dir, args.name, args.allow_dirty)}")


if __name__ == '__main__':
    main()
