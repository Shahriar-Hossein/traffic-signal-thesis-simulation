"""
Export a self-contained results package outside the ignored `data/` tree.

`data/*` is gitignored, so anything that lives only there cannot be cited,
reviewed or reproduced from the repository. This copies the plans, raw logs
and derived analyses into `results/<name>/` together with the revisions that
produced them and the commands that reproduce them.

    python3 scripts/export_results.py --name pilot_2026_09_10 \\
        --baseline fixed data/paired/even_500_seed301

Two revisions, never one. The working-tree commit here is the revision of the
*analysis and export* code, which normally runs later than the simulation.
The revision that produced the runs is identified by the source fingerprints
each arm recorded at startup, and the manifest carries both — with the
fingerprints resolved against git where possible, so the archive says how to
check out the code that produced it rather than merely that it differed.

The analysis specification travels with the package too. Recomputing a
comparison under default tolerances and an inferred baseline is not the
comparison that was reported: inferring the baseline from run order can
reverse the contrast outright.

Refuses to export from a dirty working tree unless --allow-dirty is given: a
package whose revision does not describe its own code is not reproducible.
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from analyzers.analyze_paired import (  # noqa: E402
    ANALYSIS_SCHEMA_VERSION, DEFAULT_DRIFT_TOLERANCE_MS, DEFAULT_FPS_TOLERANCE,
    analyze_pair, load_arm,
)
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


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_revisions(plan_dir):
    """
    The source fingerprints each arm recorded when it started.

    These identify the bytes the simulation ran; the export's own commit does
    not. Where a fingerprint matches a blob git still holds, the checkout
    recipe for it is recorded beside it, so "which code produced this" has an
    answer that can be acted on.
    """
    revisions = {}
    for arm_dir in arm_dirs(plan_dir):
        arm = load_arm(arm_dir)
        meta = arm.get('meta') if isinstance(arm.get('meta'), dict) else {}
        sources = meta.get('source_files')
        revisions[os.path.basename(arm_dir)] = {
            'source_hash': meta.get('source_hash'),
            'configuration_hash': meta.get('configuration_hash'),
            'files_recorded': len(sources) if isinstance(sources, dict) else 0,
            'started_at': meta.get('started_at'),
            'checkout': checkout_recipe(sources),
        }
    return revisions


def blob_bytes(reference):
    """A git object's exact bytes. Text mode would mangle line endings."""
    try:
        return subprocess.run(['git', '-C', ROOT, 'cat-file', 'blob', reference],
                              capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def checkout_recipe(sources, search_depth=60):
    """
    A commit whose tracked files match the recorded fingerprints, if there is
    one. `None` means the run's source bytes are not retrievable from this
    repository — which is a finding about reproducibility, not a formatting
    detail, and is the honest answer for a run made from an uncommitted tree.
    """
    if not isinstance(sources, dict) or not sources:
        return None
    tracked = {name: content for name, content in sources.items()
               if not name.startswith('images/')}
    if not tracked:
        return None

    for commit in (git('rev-list', '-n', str(search_depth), 'HEAD') or '').split():
        listing = git('ls-tree', '-r', commit)
        if not listing:
            continue
        blobs = {}
        for line in listing.splitlines():
            info, _, name = line.partition('\t')
            blobs[name] = info.split()[2]
        if not all(name in blobs for name in tracked):
            continue
        if all(hashlib.sha256(blob_bytes(blobs[name]) or b'\0').hexdigest() == content
               for name, content in tracked.items()):
            return {'commit': commit, 'command': f'git checkout {commit}'}
    return None


def export_plan(plan_dir, destination, analysis):
    """
    Copy one plan folder's inputs and outputs, and derive its analyses.

    The analyses run against the *copied* snapshot, so what the package
    reports is what the package contains: analysing the mutable source folder
    and then copying it leaves the two free to disagree.
    """
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

    revisions = run_revisions(target)

    comparison = analyze_pair(
        target, write=False,
        baseline=analysis['baseline'],
        fps_tolerance=analysis['fps_tolerance'],
        drift_tolerance_ms=analysis['drift_tolerance_ms'],
    )
    timing = analyze_timing(target, write=False)
    discharge = [analyze_discharge(arm_dir) for arm_dir in arm_dirs(target)]
    for filename, payload in (('comparison.json', comparison),
                              ('timing.json', timing),
                              ('discharge.json', discharge)):
        with open(os.path.join(target, filename), 'w') as handle:
            json.dump(payload, handle, indent=2)

    return {'plan_id': name, 'comparison': comparison, 'timing': timing,
            'discharge': discharge, 'run_revisions': revisions,
            'target': target}


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


def export(plan_dirs, name, allow_dirty=False, baseline=None,
           fps_tolerance=DEFAULT_FPS_TOLERANCE,
           drift_tolerance_ms=DEFAULT_DRIFT_TOLERANCE_MS):
    info = revision()
    if info['dirty'] and not allow_dirty:
        raise SystemExit(
            'refusing to export from a dirty working tree; commit first '
            'or pass --allow-dirty'
        )

    plan_dirs = [os.path.abspath(directory) for directory in plan_dirs]
    basenames = [os.path.basename(directory.rstrip(os.sep)) for directory in plan_dirs]
    repeated = sorted({label for label in basenames if basenames.count(label) > 1})
    if repeated:
        # Two folders with one basename would be merged into one directory,
        # and the package would silently contain a blend of both.
        raise SystemExit(
            f'plan folders share a name and would overwrite each other: {repeated}'
        )

    destination = os.path.join(RESULTS_ROOT, name)
    if os.path.exists(destination):
        raise SystemExit(f'{destination} already exists; choose another --name')

    analysis = {
        'baseline': baseline,
        'fps_tolerance': fps_tolerance,
        'drift_tolerance_ms': drift_tolerance_ms,
        'schema_version': ANALYSIS_SCHEMA_VERSION,
    }

    # Staged and renamed into place, so a failure part-way through cannot
    # leave something that looks like a finished package.
    staging = destination + '.partial'
    if os.path.exists(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    try:
        exports = [export_plan(directory, staging, analysis) for directory in plan_dirs]
        write_manifest(staging, name, info, analysis, exports, plan_dirs)
        with open(os.path.join(staging, 'SUMMARY.md'), 'w') as handle:
            handle.write('\n'.join(summary_lines(exports)) + '\n')
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    os.replace(staging, destination)

    return destination


def write_manifest(destination, name, info, analysis, exports, plan_dirs):
    """Everything needed to say what was analysed, by what, and from where."""
    files = {}
    for root, _, filenames in os.walk(destination):
        for filename in sorted(filenames):
            path = os.path.join(root, filename)
            files[os.path.relpath(path, destination)] = digest(path)

    command = (f"python3 scripts/export_results.py --name {name}"
               + (f" --baseline {analysis['baseline']}" if analysis['baseline'] else '')
               + f" --fps-tolerance {analysis['fps_tolerance']}"
               + f" --drift-tolerance-ms {analysis['drift_tolerance_ms']} "
               + ' '.join(plan_dirs))

    manifest = {
        'name': name,
        'exported_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        # The revision of the code that did the analysis and the export. It is
        # not evidence about the revision the simulation ran under.
        'analysis_revision': info,
        # What each arm recorded about its own code, at the moment it ran.
        'run_revisions': {export['plan_id']: export['run_revisions']
                          for export in exports},
        'analysis': analysis,
        'python': platform.python_version(),
        'platform': platform.platform(),
        'packages': installed_packages(),
        'plans': [export['plan_id'] for export in exports],
        'file_digests': files,
        'commands': {
            'export': command,
            'pair': (f"python3 analyzers/analyze_paired.py <plan_dir>"
                     + (f" --baseline {analysis['baseline']}" if analysis['baseline'] else '')),
            'batch': 'python3 analyzers/analyze_paired.py --batch data/paired',
            'timing': 'python3 analyzers/analyze_timing.py <plan_dir>',
            'discharge': 'python3 analyzers/analyze_discharge.py <arm_dir>',
        },
    }
    with open(os.path.join(destination, 'manifest.json'), 'w') as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


def installed_packages():
    """The runtime the analysis ran on, so a rerun can match it."""
    try:
        from importlib import metadata
        return {dist.metadata['Name']: dist.version
                for dist in sorted(metadata.distributions(),
                                   key=lambda d: (d.metadata['Name'] or '').lower())
                if dist.metadata['Name']}
    except Exception:
        return {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('plan_dir', nargs='+', help='data/paired/{plan_id} folders')
    parser.add_argument('--name', required=True, help='package name under results/')
    parser.add_argument('--allow-dirty', action='store_true',
                        help='export even though the working tree has changes')
    parser.add_argument('--baseline',
                        help='arm to compare the others against; recorded in '
                             'the manifest. Without it the baseline is '
                             'inferred from run order, which can reverse a '
                             'contrast.')
    parser.add_argument('--fps-tolerance', type=float, default=DEFAULT_FPS_TOLERANCE)
    parser.add_argument('--drift-tolerance-ms', type=float,
                        default=DEFAULT_DRIFT_TOLERANCE_MS)
    args = parser.parse_args(argv)
    print(f"✅ Exported to {export(args.plan_dir, args.name, args.allow_dirty, args.baseline, args.fps_tolerance, args.drift_tolerance_ms)}")


if __name__ == '__main__':
    main()
