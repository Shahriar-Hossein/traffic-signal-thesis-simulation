"""Immutable startup fingerprints for replay audits (no simulation imports)."""
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import sys


def fingerprint(value):
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(',', ':'), allow_nan=False,
    ).encode()).hexdigest()


def _installed_version(package):
    """Return one relevant dependency version without importing the package."""
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return None


def _runtime_snapshot():
    """Capture startup runtime facts without collecting the environment."""
    return {
        'python_implementation': platform.python_implementation(),
        'python_version': platform.python_version(),
        'pygame_version': _installed_version('pygame'),
        'os': platform.system(),
        'os_release': platform.release(),
        'platform': platform.platform(),
        'machine': platform.machine(),
        'sdl_video_driver': os.environ.get('SDL_VIDEODRIVER'),
        'executable': sys.executable,
        'argv': list(sys.argv),
    }


def runtime_identity(runtime):
    """Select runtime fields suitable for comparing two environments."""
    return {
        key: runtime[key] for key in (
            'python_implementation', 'python_version', 'pygame_version',
            'os', 'os_release', 'platform', 'machine', 'sdl_video_driver',
        )
    }


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
    runtime = _runtime_snapshot()
    identity = runtime_identity(runtime)
    return {
        'provenance_version': 1,
        'configuration': snapshot,
        'configuration_hash': fingerprint(snapshot),
        'source_files': sources,
        'source_hash': fingerprint(sources),
        'runtime': runtime,
        'runtime_identity': identity,
        'runtime_identity_hash': fingerprint(identity),
    }
