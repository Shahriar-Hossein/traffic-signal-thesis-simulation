"""Validated fixed-timing tables for the executable tuned comparator."""
import json


SCHEMA_VERSION = 1
GREEN_COUNT = 4
GREEN_MIN = 6
GREEN_MAX = 60
RESERVED_SEEDS = set(range(9001, 9021))


def load_fixed_timing(path):
    """Load and fail closed on a fixed-timing selection table."""
    with open(path) as handle:
        table = json.load(handle)
    if not isinstance(table, dict):
        raise ValueError('fixed timing plan must be an object')
    if table.get('schema_version') != SCHEMA_VERSION:
        raise ValueError('unsupported fixed timing schema_version')

    seeds = table.get('development_seeds')
    if (not isinstance(seeds, list) or not seeds
            or any(type(seed) is not int for seed in seeds)):
        raise ValueError('development_seeds must be a nonempty list of integers')
    if any(seed in RESERVED_SEEDS for seed in seeds):
        raise ValueError('development_seeds contain reserved evaluation seeds')

    method = table.get('selection_method')
    if not isinstance(method, str) or not method.strip():
        raise ValueError('selection_method must be a nonempty string')

    scenarios = table.get('scenarios')
    if not isinstance(scenarios, dict) or not scenarios:
        raise ValueError('scenarios must be a nonempty mapping')
    for label, greens in scenarios.items():
        if not isinstance(label, str) or not label:
            raise ValueError('scenario labels must be nonempty strings')
        mode, condition, count_text = label.rsplit('_', 2) if label.count('_') >= 2 else ('', '', '')
        if (not mode or condition not in ('low', 'medium', 'high', 'mixed')
                or not count_text.isdigit() or int(count_text) <= 0):
            raise ValueError(f'scenario label {label!r} is not canonical')
        if (not isinstance(greens, list) or len(greens) != GREEN_COUNT
                or any(type(green) is not int
                       or not GREEN_MIN <= green <= GREEN_MAX
                       for green in greens)):
            raise ValueError(
                f'scenario {label!r} must contain four integer greens '
                f'between {GREEN_MIN} and {GREEN_MAX} seconds'
            )
    return table


def resolve_fixed_greens(table, plan_header):
    """Resolve a validated table's greens for one plan header."""
    if not isinstance(table, dict) or not isinstance(plan_header, dict):
        raise ValueError('fixed timing table and plan header must be objects')
    mode = plan_header.get('uneven_mode')
    count = plan_header.get('target_vehicle_count')
    if not isinstance(mode, str) or not mode or type(count) is not int or count <= 0:
        raise ValueError('plan header has no valid scenario identity')
    condition = plan_header.get('pinned_condition') or 'mixed'
    if not isinstance(condition, str) or not condition:
        raise ValueError('plan header has an invalid pinned_condition')
    key = f'{mode}_{condition}_{count}'
    try:
        greens = table['scenarios'][key]
    except (KeyError, TypeError):
        raise ValueError(f'fixed timing plan has no scenario {key!r}') from None
    if (not isinstance(greens, list) or len(greens) != GREEN_COUNT
            or any(type(green) is not int
                   or not GREEN_MIN <= green <= GREEN_MAX
                   for green in greens)):
        raise ValueError(f'fixed timing plan has invalid greens for {key!r}')
    return tuple(greens)
