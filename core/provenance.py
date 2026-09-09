"""Immutable startup fingerprints for replay audits (no simulation imports)."""
import hashlib
import json
from pathlib import Path


def fingerprint(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode()).hexdigest()


def capture_provenance(config, timeout):
    # Round-trip now: config.x/y are mutated later as vehicles spawn.
    snapshot = json.loads(json.dumps({
        key: value for key, value in vars(config).items()
        if not key.startswith('_')
    }))
    snapshot['count_mode_timeout'] = timeout
    root = Path(__file__).resolve().parents[1]
    paths = [root / name for name in ('main.py', 'state.py', 'config.py')]
    for directory in ('core', 'models', 'utils'):
        paths.extend((root / directory).glob('*.py'))
    paths.extend((root / 'images').rglob('*.png'))
    sources = {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
               for path in sorted(paths)}
    return {
        'provenance_version': 1,
        'configuration': snapshot,
        'configuration_hash': fingerprint(snapshot),
        'source_files': sources,
        'source_hash': fingerprint(sources),
    }
