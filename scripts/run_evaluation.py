#!/usr/bin/env python3
"""Prepare, resume, and analyze the frozen held-out evaluation."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analyzers.analyze_paired import analyze_batch, analyze_pair  # noqa: E402
import config as runtime_config  # noqa: E402
from core.fixed_timing import RESERVED_SEEDS, load_fixed_timing  # noqa: E402
from core.plan import build_plan, default_plan_id, load_plan, write_plan  # noqa: E402
from core.provenance import (capture_provenance, fingerprint, runtime_identity,
                             _runtime_snapshot)  # noqa: E402
from scripts.scenarios import scenarios  # noqa: E402

DEFAULT_SEEDS = tuple(range(9001, 9014))
ARMS = (
    ('fixed', 'fixed'),
    ('priority', 'priority'),
    ('fixed_order_adaptive_duration', 'fixed_order_adaptive_duration'),
    ('adaptive_order_fixed_duration', 'adaptive_order_fixed_duration'),
    ('actuated', 'actuated'),
    ('fixed_tuned', 'fixed_tuned'),
)
WORKFLOW_FILES = (
    'scripts/run_evaluation.py', 'run_paired.py',
    'analyzers/analyze_paired.py', 'analyzers/analyze_timing.py',
    'scripts/scenarios.py',
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write('\n')


def scenario_key(cell, count):
    return f"{cell['uneven_mode']}_{cell['condition'] or 'mixed'}_{count}"


def _selected_table(path, count):
    raw = Path(path).read_bytes()
    table = load_fixed_timing(path)
    expected = {scenario_key(cell, count) for cell in scenarios()}
    if set(table['scenarios']) != expected:
        raise ValueError('selected fixed timing must cover exactly all 12 evaluation cells')
    evidence = table.get('evidence')
    if not isinstance(evidence, dict) or set(evidence) != expected:
        raise ValueError('selected fixed timing must contain evidence for every cell')
    for key, record in evidence.items():
        if (not isinstance(record, dict)
                or not isinstance(record.get('selected_candidate'), str)
                or not record['selected_candidate'].strip()
                or not isinstance(record.get('candidate_delay_means_sec'), dict)
                or not record['candidate_delay_means_sec']
                or not all(isinstance(value, (int, float)) and math.isfinite(value)
                           for value in record['candidate_delay_means_sec'].values())
                or record['selected_candidate'] not in record['candidate_delay_means_sec']):
            raise ValueError(f'selection evidence is incomplete for {key}')
    hashes = table.get('source_hashes')
    if not isinstance(hashes, dict):
        raise ValueError('selected fixed timing has no source_hashes')
    simulator_hash = (hashes.get('run_simulator_source_hash')
                      or hashes.get('simulator_source_hash'))
    runtime_hash = hashes.get('runtime_identity_hash')
    if (not isinstance(simulator_hash, str) or not simulator_hash
            or not isinstance(runtime_hash, str) or not runtime_hash
            or not isinstance(hashes.get('manifest_sha256'), str)
            or not isinstance(hashes.get('candidate_inputs_sha256'), dict)
            or not hashes['candidate_inputs_sha256']):
        raise ValueError('selected fixed timing has incomplete source provenance')
    return raw, table, simulator_hash, runtime_hash


def _frozen_protocol(path, freeze_note):
    if not isinstance(freeze_note, str) or not freeze_note.strip():
        raise ValueError('--freeze-note must record the protocol freeze decision')
    raw = Path(path).read_bytes()
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError('protocol must be UTF-8 text') from error
    if not re.search(r'(?mi)^\s*Status:\s*frozen\s*$', text):
        raise ValueError('protocol must contain an explicit line: Status: frozen')
    return raw


def _validate_seeds(seeds):
    if (not seeds or len(set(seeds)) != len(seeds)
            or any(type(seed) is not int or seed not in RESERVED_SEEDS for seed in seeds)):
        raise ValueError('evaluation seeds must be unique reserved integer seeds')


def _copy_inventory(destination, inventory, folder):
    for name, expected in inventory.items():
        source = ROOT / name
        archived = destination / folder / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, archived)
        if digest(archived) != expected:
            raise ValueError(f'could not preserve exact snapshot: {name}')


def prepare(destination, selected_timing, protocol, freeze_note,
            seeds=DEFAULT_SEEDS, count=500, timeout=3000):
    """Write held-out plans and a frozen manifest; never run simulations."""
    destination = Path(destination).resolve()
    selected_timing, protocol = Path(selected_timing).resolve(), Path(protocol).resolve()
    _validate_seeds(tuple(seeds))
    if type(count) is not int or count <= 0 or type(timeout) is not int or timeout <= 0:
        raise ValueError('count and timeout must be positive integers')
    if destination.exists():
        raise ValueError(f'destination already exists: {destination}')
    timing_raw, _, selected_source, selected_runtime = _selected_table(
        selected_timing, count)
    protocol_raw = _frozen_protocol(protocol, freeze_note)
    provenance = capture_provenance(runtime_config, timeout)
    if (provenance['source_hash'] != selected_source
            or provenance['runtime_identity_hash'] != selected_runtime):
        raise ValueError('selected timing evidence differs from current source or runtime')

    destination.mkdir(parents=True)
    archived_timing = destination / 'inputs' / 'fixed_timing.json'
    archived_protocol = destination / 'inputs' / 'protocol.md'
    archived_timing.parent.mkdir(parents=True)
    archived_timing.write_bytes(timing_raw)
    archived_protocol.write_bytes(protocol_raw)
    _copy_inventory(destination, provenance['source_files'], 'source')
    workflow = {name: digest(ROOT / name) for name in WORKFLOW_FILES}
    _copy_inventory(destination, workflow, 'workflow')

    plans, pairs = [], []
    for cell in scenarios():
        scenario = scenario_key(cell, count)
        for seed_index, seed in enumerate(seeds):
            plan_id = default_plan_id(cell['uneven_mode'], count, seed,
                                      cell['condition'])
            plan_path = destination / 'plans' / plan_id / 'plan.json'
            write_plan(build_plan(seed, count, cell['uneven_mode'], plan_id=plan_id,
                                  condition=cell['condition']), str(plan_path))
            header = load_plan(plan_path)['header']
            plans.append({
                'scenario': scenario, 'seed': seed, 'plan_id': plan_id,
                'plan': str(plan_path.relative_to(destination)),
                'plan_hash': header['content_hash'], 'input_sha256': digest(plan_path),
            })
            offset = seed_index % len(ARMS)
            ordered = ARMS[offset:] + ARMS[:offset]
            output = destination / 'results'
            log = destination / 'logs' / f'{plan_id}.log'
            argv = [
                sys.executable, '-u', str(ROOT / 'run_paired.py'),
                '--plan', str(plan_path), '--output-root', str(output),
                '--arms', *(label if label == controller else f'{label}={controller}'
                            for label, controller in ordered),
                '--baseline', 'fixed', '--fixed-timing-plan', str(archived_timing),
                '--timeout', str(timeout),
            ]
            pairs.append({
                'scenario': scenario, 'seed': seed, 'seed_index': seed_index,
                'plan_id': plan_id, 'arm_order': [label for label, _ in ordered],
                'result_dir': str((output / plan_id).relative_to(destination)),
                'stdout_log': str(log.relative_to(destination)),
                'argv': argv, 'command': shlex.join(argv),
            })
    manifest = {
        'schema_version': 1, 'purpose': 'FINAL held-out evaluation',
        'evaluation_seeds': list(seeds), 'count': count, 'timeout': timeout,
        'baseline': 'fixed', 'arms': [list(item) for item in ARMS],
        'plans': plans, 'pairs': pairs,
        'inputs': {
            'selected_timing': str(archived_timing.relative_to(destination)),
            'selected_timing_sha256': digest(archived_timing),
            'selected_timing_source': str(selected_timing),
            'protocol': str(archived_protocol.relative_to(destination)),
            'protocol_sha256': digest(archived_protocol),
            'protocol_source': str(protocol), 'freeze_note': freeze_note.strip(),
        },
        'frozen_simulator': {
            'source_files': provenance['source_files'],
            'source_hash': provenance['source_hash'],
            'runtime_identity': provenance['runtime_identity'],
            'runtime_identity_hash': provenance['runtime_identity_hash'],
        },
        'frozen_workflow': {'files': workflow, 'source_hash': fingerprint(workflow)},
    }
    _write_json(destination / 'manifest.json', manifest)
    return manifest


def _validated_manifest(destination, current=True):
    destination = Path(destination).resolve()
    manifest = json.loads((destination / 'manifest.json').read_text())
    _validate_seeds(tuple(manifest['evaluation_seeds']))
    inputs = manifest['inputs']
    for key in ('selected_timing', 'protocol'):
        archived = destination / inputs[key]
        if digest(archived) != inputs[f'{key}_sha256']:
            raise ValueError(f'archived {key} bytes differ from manifest')
        if current and digest(inputs[f'{key}_source']) != inputs[f'{key}_sha256']:
            raise ValueError(f'current {key} differs from frozen input')
    _frozen_protocol(destination / inputs['protocol'], inputs['freeze_note'])
    _selected_table(destination / inputs['selected_timing'], manifest['count'])

    for folder, inventory_key, hash_key in (
            ('source', 'source_files', 'source_hash'),
            ('workflow', 'files', 'source_hash')):
        record = manifest['frozen_simulator' if folder == 'source'
                          else 'frozen_workflow']
        inventory = record[inventory_key]
        if not inventory or fingerprint(inventory) != record[hash_key]:
            raise ValueError(f'frozen {folder} inventory is inconsistent')
        for name, expected in inventory.items():
            if digest(destination / folder / name) != expected:
                raise ValueError(f'frozen {folder} snapshot mismatch: {name}')
            if current and digest(ROOT / name) != expected:
                raise ValueError(f'current {folder} differs from manifest: {name}')
    frozen = manifest['frozen_simulator']
    if current:
        identity = runtime_identity(_runtime_snapshot())
        if (identity != frozen['runtime_identity']
                or fingerprint(identity) != frozen['runtime_identity_hash']):
            raise ValueError('current runtime differs from manifest')

    expected = {(scenario_key(cell, manifest['count']), seed)
                for cell in scenarios() for seed in manifest['evaluation_seeds']}
    recorded = {(item['scenario'], item['seed']) for item in manifest['plans']}
    if recorded != expected or len(recorded) != len(manifest['plans']):
        raise ValueError('manifest plan coverage is missing or duplicated')
    for record in manifest['plans']:
        path = destination / record['plan']
        header = load_plan(path)['header']
        if (digest(path) != record['input_sha256']
                or header['content_hash'] != record['plan_hash']
                or header['plan_id'] != record['plan_id']
                or header['seed'] != record['seed']):
            raise ValueError(f"plan provenance mismatch: {record['plan_id']}")
    if (len(manifest['pairs']) != len(expected)
            or {(p['scenario'], p['seed']) for p in manifest['pairs']} != expected):
        raise ValueError('pair schedule coverage differs from plan coverage')
    labels = [item[0] for item in ARMS]
    for entry in manifest['pairs']:
        offset = entry['seed_index'] % len(labels)
        if entry['arm_order'] != labels[offset:] + labels[:offset]:
            raise ValueError(f"arm order drift: {entry['plan_id']}")
    return manifest


def _complete_pair(destination, entry):
    path = destination / entry['result_dir']
    comparison = analyze_pair(str(path), write=False, baseline='fixed')
    expected = {label for label, _ in ARMS}
    if (not comparison.get('publication_eligible', comparison.get('valid'))
            or set(comparison.get('arm_names', ())) != expected
            or comparison.get('baseline_arm') != 'fixed'
            or comparison.get('plan_id') != entry['plan_id']):
        reasons = '; '.join(comparison.get('invalid_reasons') or ['wrong arms or plan'])
        raise ValueError(f'existing pair is incomplete or invalid: {path}: {reasons}')
    return comparison


def collection_status(destination, manifest):
    complete = sum((destination / item['result_dir']).exists()
                   for item in manifest['pairs'])
    return {'pairs_scheduled': len(manifest['pairs']), 'pairs_complete': complete,
            'pairs_remaining': len(manifest['pairs']) - complete}


def run_manifest(destination, max_pairs=None):
    """Run absent pairs serially; never retry or overwrite an existing pair."""
    destination = Path(destination).resolve()
    manifest = _validated_manifest(destination)
    if max_pairs is not None and (type(max_pairs) is not int or max_pairs < 0):
        raise ValueError('--max-pairs must be a nonnegative integer')
    launched = 0
    for entry in manifest['pairs']:
        pair_dir = destination / entry['result_dir']
        if pair_dir.exists():
            _complete_pair(destination, entry)
            continue
        if max_pairs is not None and launched >= max_pairs:
            break
        _validated_manifest(destination)
        log_path = destination / entry['stdout_log']
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open('x') as log:
            process = subprocess.Popen(entry['argv'], cwd=ROOT, text=True,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, bufsize=1)
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
            returncode = process.wait()
        if returncode:
            raise RuntimeError(f'pair failed; no retry allowed; log: {log_path}')
        _complete_pair(destination, entry)
        launched += 1
    status = collection_status(destination, manifest)
    status['pairs_launched'] = launched
    return status


def analyze(destination):
    """Write one explicit-plan analysis for each scenario cell."""
    destination = Path(destination).resolve()
    manifest = _validated_manifest(destination, current=False)
    for entry in manifest['pairs']:
        if not (destination / entry['result_dir']).exists():
            raise ValueError(f"evaluation is incomplete: missing {entry['plan_id']}")
        _complete_pair(destination, entry)
    reports = {}
    for scenario in sorted({item['scenario'] for item in manifest['plans']}):
        plan_ids = [item['plan_id'] for item in manifest['plans']
                    if item['scenario'] == scenario]
        report = analyze_batch(str(destination / 'results'), write=False,
                               baseline='fixed', plan_ids=plan_ids)
        if (report['plans_total'] != len(plan_ids) or report['plans_invalid']
                or report['duplicate_plans'] or report['cohort_errors']):
            raise ValueError(f'analysis rejected scenario {scenario}')
        path = destination / 'analysis' / f'{scenario}.json'
        _write_json(path, report)
        reports[scenario] = str(path.relative_to(destination))
    result = {**collection_status(destination, manifest),
              'baseline': 'fixed', 'scenario_reports': reports}
    _write_json(destination / 'analysis' / 'index.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('destination')
    prep.add_argument('--selected-timing', required=True)
    prep.add_argument('--protocol', required=True)
    prep.add_argument('--freeze-note', required=True)
    prep.add_argument('--seeds', type=int, nargs='+', default=list(DEFAULT_SEEDS))
    prep.add_argument('--count', type=int, default=500)
    prep.add_argument('--timeout', type=int, default=3000)
    run = commands.add_parser('run')
    run.add_argument('destination')
    run.add_argument('--max-pairs', type=int)
    report = commands.add_parser('analyze')
    report.add_argument('destination')
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare':
            result = prepare(args.destination, args.selected_timing, args.protocol,
                             args.freeze_note, tuple(args.seeds), args.count,
                             args.timeout)
            result = collection_status(Path(args.destination).resolve(), result)
        elif args.action == 'run':
            result = run_manifest(args.destination, args.max_pairs)
        else:
            result = analyze(args.destination)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (OSError, ValueError, RuntimeError, KeyError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == '__main__':
    sys.exit(main())
