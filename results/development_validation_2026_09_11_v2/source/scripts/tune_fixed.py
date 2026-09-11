#!/usr/bin/env python3
"""Prepare, optionally run, and select development-only fixed timings."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shlex
import shutil
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzers.analyze_paired import analyze_pair, load_arm  # noqa: E402
import config as runtime_config  # noqa: E402
from core.fixed_timing import RESERVED_SEEDS, load_fixed_timing  # noqa: E402
from core.plan import (build_plan, default_plan_id, direction_weights,
                       load_plan, write_plan)  # noqa: E402
from core.provenance import (capture_provenance, fingerprint, runtime_identity,
                             _runtime_snapshot)  # noqa: E402
from scripts.scenarios import scenarios  # noqa: E402

CANDIDATES = ('uniform12', 'uniform24', 'demand_split96')
DEFAULT_SEEDS = (301, 302)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def scenario_key(cell, count):
    return f"{cell['uneven_mode']}_{cell['condition'] or 'mixed'}_{count}"


def allocate_green(total, weights, minimum=6, maximum=60):
    """Constrained proportional allocation with deterministic remainders."""
    if (type(total) is not int or not weights or any(w < 0 for w in weights)
            or not minimum * len(weights) <= total <= maximum * len(weights)):
        raise ValueError('infeasible green allocation')
    active, fixed = set(range(len(weights))), {}
    remaining = float(total)
    while active:
        weight_sum = sum(weights[i] for i in active)
        if weight_sum <= 0:
            shares = {i: remaining / len(active) for i in active}
        else:
            shares = {i: remaining * weights[i] / weight_sum for i in active}
        clipped = False
        for i in sorted(active):
            bound = minimum if shares[i] < minimum else maximum if shares[i] > maximum else None
            if bound is not None:
                fixed[i] = float(bound)
                remaining -= bound
                active.remove(i)
                clipped = True
                break
        if not clipped:
            fixed.update(shares)
            break
    result = [math.floor(fixed[i]) for i in range(len(weights))]
    left = total - sum(result)
    order = sorted(range(len(weights)), key=lambda i: (-(fixed[i] - result[i]), i))
    for i in order[:left]:
        result[i] += 1
    if sum(result) != total or any(not minimum <= value <= maximum for value in result):
        raise AssertionError('allocation failed to preserve constraints')
    return result


def candidate_scenarios(count=500):
    tables = {name: {} for name in CANDIDATES}
    for cell in scenarios():
        key = scenario_key(cell, count)
        tables['uniform12'][key] = [12] * 4
        tables['uniform24'][key] = [24] * 4
        tables['demand_split96'][key] = allocate_green(
            96, direction_weights(cell['uneven_mode']))
    return tables


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as handle:
        json.dump(value, handle, indent=2, allow_nan=False, sort_keys=True)
        handle.write('\n')


def validate_seeds(seeds):
    if not seeds or any(type(seed) is not int for seed in seeds):
        raise ValueError('development seeds must be integers')
    held_out = sorted(set(seeds) & RESERVED_SEEDS)
    if held_out:
        raise ValueError(f'reserved evaluation seeds are forbidden: {held_out}')
    if len(set(seeds)) != len(seeds):
        raise ValueError('development seeds must be unique')


def _validate_frozen_source(destination, manifest, current=True):
    frozen = manifest.get('frozen_simulator') or {}
    files = frozen.get('source_files')
    if not isinstance(files, dict) or not files:
        raise ValueError('manifest has no frozen simulator source inventory')
    for name, expected in files.items():
        archived = destination / 'source' / name
        if not archived.is_file() or digest(archived) != expected:
            raise ValueError(f'frozen source snapshot mismatch: {name}')
        if current:
            live = ROOT / name
            if not live.is_file() or digest(live) != expected:
                raise ValueError(f'current simulator source differs from manifest: {name}')
    if fingerprint(files) != frozen.get('source_hash'):
        raise ValueError('frozen simulator source hash is inconsistent')
    if current:
        identity = runtime_identity(_runtime_snapshot())
        if (identity != frozen.get('runtime_identity')
                or fingerprint(identity) != frozen.get('runtime_identity_hash')):
            raise ValueError('current runtime differs from manifest')


def _validated_manifest(destination, current=True):
    path = destination / 'manifest.json'
    manifest = json.loads(path.read_text())
    validate_seeds(manifest['development_seeds'])
    _validate_frozen_source(destination, manifest, current)
    if current and digest(Path(__file__)) != manifest.get('tuning_workflow_sha256'):
        raise ValueError('current tuning workflow differs from manifest')
    if manifest.get('candidate_order') != list(CANDIDATES):
        raise ValueError('manifest candidate order differs from the predeclared candidates')
    expected_tables = candidate_scenarios(manifest['count'])
    loaded_tables = {}
    for name in CANDIDATES:
        record = manifest['candidates'][name]
        timing_path = destination / record['timing_table']
        if digest(timing_path) != record['input_sha256']:
            raise ValueError(f'candidate input digest mismatch: {name}')
        table = load_fixed_timing(timing_path)
        if (table.get('candidate_name') != name
                or table['development_seeds'] != manifest['development_seeds']
                or table['scenarios'] != expected_tables[name]):
            raise ValueError(f'candidate input is not the predeclared schedule: {name}')
        loaded_tables[name] = table
    for record in manifest['plans']:
        plan_path = destination / record['plan']
        if digest(plan_path) != record['input_sha256']:
            raise ValueError(f"plan input digest mismatch: {record['plan_id']}")
        header = load_plan(plan_path)['header']
        if (header['content_hash'] != record['plan_hash']
                or header['plan_id'] != record['plan_id']
                or header['seed'] != record['seed']):
            raise ValueError(f"plan provenance mismatch: {record['plan_id']}")
    expected_coverage = {
        (scenario_key(cell, manifest['count']), seed)
        for cell in scenarios() for seed in manifest['development_seeds']
    }
    recorded_coverage = {(item['scenario'], item['seed']) for item in manifest['plans']}
    if (recorded_coverage != expected_coverage
            or len(recorded_coverage) != len(manifest['plans'])):
        raise ValueError('manifest plan coverage is missing or duplicated')
    return manifest, loaded_tables


def prepare(destination, seeds=DEFAULT_SEEDS, count=500, timeout=3000):
    """Create inputs and an exact sequential manifest; never run simulations."""
    destination = Path(destination).resolve()
    validate_seeds(seeds)
    if type(count) is not int or count <= 0 or type(timeout) is not int or timeout <= 0:
        raise ValueError('count and timeout must be positive integers')
    if destination.exists():
        raise ValueError(f'destination already exists: {destination}')
    provenance = capture_provenance(runtime_config, timeout)
    destination.mkdir(parents=True)
    for name, expected in provenance['source_files'].items():
        source = ROOT / name
        archived = destination / 'source' / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, archived)
        if digest(archived) != expected:
            raise ValueError(f'could not preserve exact source snapshot: {name}')
    entries, plan_records, candidate_records = [], [], {}
    tables = candidate_scenarios(count)
    for name in CANDIDATES:
        path = destination / 'candidates' / name / 'fixed_timing.json'
        _write_json(path, {
            'schema_version': 1,
            'candidate_name': name,
            'development_seeds': list(seeds),
            'selection_method': 'predeclared development candidate; selection pending',
            'scenarios': tables[name],
        })
        candidate_records[name] = {
            'timing_table': str(path.relative_to(destination)),
            'input_sha256': digest(path),
        }
    for cell in scenarios():
        for seed in seeds:
            plan_id = default_plan_id(cell['uneven_mode'], count, seed,
                                      cell['condition'])
            plan_path = destination / 'plans' / plan_id / 'plan.json'
            plan = build_plan(seed, count, cell['uneven_mode'], plan_id=plan_id,
                              condition=cell['condition'])
            write_plan(plan, str(plan_path))
            header = load_plan(plan_path)['header']
            plan_records.append({
                'scenario': scenario_key(cell, count), 'seed': seed,
                'plan_id': plan_id, 'plan': str(plan_path.relative_to(destination)),
                'plan_hash': header['content_hash'], 'input_sha256': digest(plan_path),
            })
            for candidate in CANDIDATES:
                timing = destination / candidate_records[candidate]['timing_table']
                output = destination / 'results' / candidate
                argv = [
                    sys.executable, '-u', str(ROOT / 'run_paired.py'), '--plan', str(plan_path),
                    '--output-root', str(output), '--arms', 'fixed', 'fixed_tuned',
                    '--fixed-timing-plan', str(timing), '--timeout', str(timeout),
                ]
                entries.append({
                    'candidate': candidate, 'scenario': scenario_key(cell, count),
                    'seed': seed, 'plan_id': plan_id,
                    'result_dir': str((output / plan_id).relative_to(destination)),
                    'stdout_log': str((destination / 'logs' /
                                      f'{candidate}__{plan_id}.log').relative_to(destination)),
                    'argv': argv, 'command': shlex.join(argv),
                })
    manifest = {
        'schema_version': 1, 'purpose': 'development-only fixed timing selection',
        'development_seeds': list(seeds), 'count': count,
        'candidate_order': list(CANDIDATES), 'candidates': candidate_records,
        'plans': plan_records, 'pairs': entries,
        'frozen_simulator': {
            'source_files': provenance['source_files'],
            'source_hash': provenance['source_hash'],
            'runtime_identity': provenance['runtime_identity'],
            'runtime_identity_hash': provenance['runtime_identity_hash'],
        },
        'tuning_workflow_sha256': digest(Path(__file__)),
    }
    _write_json(destination / 'manifest.json', manifest)
    return manifest


def _complete_pair(path):
    comparison = analyze_pair(str(path), write=False, baseline='fixed')
    if (not comparison.get('publication_eligible', comparison.get('valid'))
            or comparison.get('arm_names') != ['fixed', 'fixed_tuned']):
        reasons = '; '.join(comparison.get('invalid_reasons') or ['wrong arms'])
        raise ValueError(f'existing pair is incomplete or invalid: {path}: {reasons}')
    return comparison


def run_manifest(destination, max_pairs=None):
    """Run missing pairs serially; validate completed pairs and refuse failures."""
    destination = Path(destination).resolve()
    manifest, _ = _validated_manifest(destination)
    if max_pairs is not None and max_pairs < 0:
        raise ValueError('--max-pairs must be nonnegative')
    launched = 0
    for entry in manifest['pairs']:
        pair_dir = destination / entry['result_dir']
        if pair_dir.exists():
            _complete_pair(pair_dir)
            continue
        if max_pairs is not None and launched >= max_pairs:
            break
        log_path = destination / entry['stdout_log']
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _validate_frozen_source(destination, manifest, current=True)
        with log_path.open('w') as log:
            process = subprocess.run(entry['argv'], cwd=ROOT, text=True,
                                     stdout=log, stderr=subprocess.STDOUT)
        if process.returncode:
            raise RuntimeError(f"pair failed; preserved log at {log_path}")
        _complete_pair(pair_dir)
        launched += 1
    return launched


def _raw_evidence(pair_dir, expected_timing, arm_name='fixed_tuned'):
    arm = load_arm(str(pair_dir / arm_name))
    if arm.get('error'):
        raise ValueError(f'{pair_dir}: {arm["error"]}')
    try:
        values = [float(row['wait_time_sec']) for row in arm['rows']]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f'{pair_dir}: invalid raw wait_time_sec: {error}') from error
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError(f'{pair_dir}: no finite raw fixed_tuned waits')
    meta = arm.get('meta') or {}
    if (meta.get('configuration') or {}).get('fixed_timing_plan') != expected_timing:
        raise ValueError(f'{pair_dir}: recorded fixed timing input differs from candidate')
    source_hash = meta.get('source_hash')
    runtime_hash = meta.get('runtime_identity_hash')
    if not isinstance(source_hash, str) or not isinstance(runtime_hash, str):
        raise ValueError(f'{pair_dir}: missing source or runtime provenance')
    return values, source_hash, runtime_hash


def select(destination, output=None):
    """Fail closed, then choose each scenario using complete development data."""
    destination = Path(destination).resolve()
    manifest_path = destination / 'manifest.json'
    manifest, candidate_tables = _validated_manifest(destination, current=False)
    expected = {(p['scenario'], p['seed']) for p in manifest['plans']}
    by_candidate = {name: {} for name in manifest['candidate_order']}
    evidence = {}
    run_sources, run_runtimes = set(), set()
    for name in manifest['candidate_order']:
        record = manifest['candidates'][name]
        seen = set()
        for entry in (item for item in manifest['pairs'] if item['candidate'] == name):
            pair_dir = destination / entry['result_dir']
            if not pair_dir.exists():
                raise ValueError(f'missing candidate comparison: {pair_dir}')
            comparison = _complete_pair(pair_dir)
            identity = (comparison['scenario'], comparison['generation_seed'])
            if (identity != (entry['scenario'], entry['seed'])
                    or comparison['plan_hash'] != next(
                        p['plan_hash'] for p in manifest['plans']
                        if (p['scenario'], p['seed']) == identity)):
                raise ValueError(f'comparison provenance mismatch: {pair_dir}')
            if identity in seen:
                raise ValueError(f'duplicate candidate comparison: {name} {identity}')
            seen.add(identity)
            values, source_hash, runtime_hash = _raw_evidence(
                pair_dir, candidate_tables[name])
            by_candidate[name].setdefault(identity[0], []).extend(values)
            run_sources.add(source_hash)
            run_runtimes.add(runtime_hash)
        if seen != expected:
            raise ValueError(f'candidate {name} has non-identical scenario/seed coverage')
    if len(run_sources) != 1 or len(run_runtimes) != 1:
        raise ValueError('candidate comparisons do not share one source and runtime identity')
    frozen = manifest['frozen_simulator']
    if (run_sources != {frozen['source_hash']}
            or run_runtimes != {frozen['runtime_identity_hash']}):
        raise ValueError('candidate comparisons differ from the frozen simulator manifest')
    selected = {}
    for scenario in sorted({item[0] for item in expected}):
        scores = {name: statistics.fmean(by_candidate[name][scenario])
                  for name in manifest['candidate_order']}
        winner = min(manifest['candidate_order'], key=lambda name: scores[name])
        selected[scenario] = candidate_tables[winner]['scenarios'][scenario]
        evidence[scenario] = {
            'selected_candidate': winner,
            'fixed_tuned_delay_mean_sec': scores[winner],
            'candidate_delay_means_sec': scores,
            'comparison_dirs_by_candidate': {
                name: [item['result_dir'] for item in manifest['pairs']
                       if item['candidate'] == name and item['scenario'] == scenario]
                for name in manifest['candidate_order']},
        }
    result = {
        'schema_version': 1,
        'development_seeds': manifest['development_seeds'],
        'selection_method': ('lowest arithmetic mean fixed_tuned wait_time_sec from '
                             'all raw vehicle rows in each complete development scenario; '
                             'ties follow candidate_order'),
        'candidate_order': manifest['candidate_order'],
        'scenarios': selected, 'evidence': evidence,
        'source_hashes': {
            'manifest_sha256': digest(manifest_path),
            'simulator_source_hash': next(iter(run_sources)),
            'runtime_identity_hash': next(iter(run_runtimes)),
            'candidate_inputs_sha256': {
                name: manifest['candidates'][name]['input_sha256']
                for name in manifest['candidate_order']},
        },
    }
    output = Path(output).resolve() if output else destination / 'fixed_timing.json'
    if output.exists():
        raise ValueError(f'selection output already exists: {output}')
    _write_json(output, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('destination')
    prep.add_argument('--seeds', type=int, nargs='+', default=list(DEFAULT_SEEDS))
    prep.add_argument('--count', type=int, default=500)
    prep.add_argument('--timeout', type=int, default=3000)
    prep.add_argument('--run', action='store_true')
    prep.add_argument('--max-pairs', type=int)
    run = commands.add_parser('run')
    run.add_argument('destination')
    run.add_argument('--max-pairs', type=int)
    choose = commands.add_parser('select')
    choose.add_argument('destination')
    choose.add_argument('--output')
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare':
            if args.max_pairs is not None and not args.run:
                raise ValueError('--max-pairs requires --run with prepare')
            prepare(args.destination, tuple(args.seeds), args.count, args.timeout)
            if args.run:
                run_manifest(args.destination, args.max_pairs)
        elif args.action == 'run':
            run_manifest(args.destination, args.max_pairs)
        else:
            select(args.destination, args.output)
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    sys.exit(main())
