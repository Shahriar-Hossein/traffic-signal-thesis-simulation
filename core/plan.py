# core/plan.py
"""
Vehicle sampling, shared by the live generator and the replay-plan writer,
plus the plan file's schema, reader and validator.

Everything that draws a vehicle lives here and *only* here.  The live random
generator (`core.generator.generateVehicles`) and `scripts/make_plan.py` both
call `sample_vehicle` / `sample_turn`, so a plan always describes the same
distribution the live mode produces.  If the two ever had their own copy of
the draw logic they could drift apart and nothing would report it.
"""

import hashlib
import json
import os
import random
import subprocess

from config import (
    directionNumbers, vehicleTypes,
    trafficConditions, trafficConditionInterval,
    turnDirections, turnProbability,
)

# Bumped whenever the plan file's shape changes.  A plan whose version this
# code does not know is rejected loudly rather than half-read.
SCHEMA_VERSION = 1

# Same order as config.directionNumbers — the direction weight lists below are
# positional against it, exactly as the old inline table in generator.py was.
DIRECTIONS = list(directionNumbers.values())

# Lanes a vehicle can be generated into (lane 3 exists in the coordinate
# tables but is never generated into; this mirrors the original generator).
LANE_COUNT = 3

# Direction probabilities per demand skew.  Any mode not listed here — and
# `None` — falls back to uniform, which is what the original if/elif chain did.
DIRECTION_WEIGHTS = {
    # adjacent routes have more vehicles
    'down_left':   [0.15, 0.35, 0.35, 0.15],
    'right_down':  [0.35, 0.35, 0.15, 0.15],
    'right_up':    [0.35, 0.15, 0.15, 0.35],
    'left_up':     [0.15, 0.15, 0.35, 0.35],

    # one direction has more vehicles
    'up':          [0.05, 0.05, 0.05, 0.85],
    'down':        [0.05, 0.85, 0.05, 0.05],
    'left':        [0.05, 0.05, 0.85, 0.05],
    'right':       [0.85, 0.05, 0.05, 0.05],

    # alternate routes — up & down, left & right have more vehicles
    'up_down':     [0.15, 0.35, 0.15, 0.35],
    'left_right':  [0.35, 0.15, 0.35, 0.15],
}

UNIFORM_WEIGHTS = [0.25, 0.25, 0.25, 0.25]


def direction_weights(uneven_mode):
    """Direction probabilities for a demand skew ('even'/None -> uniform)."""
    return DIRECTION_WEIGHTS.get(uneven_mode, UNIFORM_WEIGHTS)


def pick_traffic_condition(previous=None, rng=random):
    """
    Pick a traffic condition ('high'/'medium'/'low'), always different from
    the one currently active.
    """
    choices = [c for c in trafficConditions if c != previous]
    return rng.choice(choices)


def sample_vehicle(uneven_mode, rng):
    """
    Draw one vehicle's type, direction and lane.

    The draw order — type, then direction, then lane — is load bearing: it is
    the order the original inline code used, so a seeded `rng` reproduces the
    old sequence exactly.  Do not reorder these three calls.
    """
    vehicle_type_index = rng.randint(0, 3)
    direction = rng.choices(DIRECTIONS, direction_weights(uneven_mode))[0]
    lane = rng.randint(0, LANE_COUNT - 1)

    return {
        'vehicle_type': vehicleTypes[vehicle_type_index],
        'direction': direction,
        'direction_number': DIRECTIONS.index(direction),
        'lane': lane,
    }


def sample_turn(direction, lane, rng):
    """
    Decide whether this vehicle turns, and into which lane.

    Lifted verbatim out of `Vehicle.__init__` so the plan writer can make the
    same decision the constructor would have made.  The draws only happen when
    the lane actually offers a turn, which is what makes the sequence match.
    """
    possible_turn = turnDirections[direction][lane]
    if possible_turn != direction and rng.random() < turnProbability:
        return {
            'will_turn': True,
            'turn_direction': possible_turn,
            'target_turn_lane': rng.randint(0, 2),
        }
    return {
        'will_turn': False,
        'turn_direction': direction,
        'target_turn_lane': 0,
    }


# --- Plan building -------------------------------------------------------

def git_rev():
    """Short git revision the plan was generated at, or None outside a repo."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def build_plan(seed, count, uneven_mode, plan_id=None):
    """
    Generate a full replay plan on a *virtual* clock.

    The clock advances by `1 / trafficConditions[condition]` per vehicle and
    switches condition on the `trafficConditionInterval` boundary — exactly
    what core/generator.py does against `time.time()`, minus the sleep drift.
    The drift is deliberately not modelled: it is a property of the machine on
    the day, not of the traffic, and both replay arms re-impose their own.

    Uses a private `random.Random(seed)`; never the global module, so nothing
    else in the process can perturb the sequence.
    """
    rng = random.Random(seed)

    vehicles = []
    timeline = []

    t = 0.0
    condition = None
    condition_started_at = None

    for seq in range(count):
        # Mirrors generator.py: the condition is picked *before* the vehicle
        # draws, so the rng sequence lines up with the live path.
        if condition is None or t - condition_started_at >= trafficConditionInterval:
            condition = pick_traffic_condition(condition, rng)
            condition_started_at = t
            timeline.append({
                't_offset_sec': round(t, 6),
                'condition': condition,
            })

        drawn = sample_vehicle(uneven_mode, rng)
        turn = sample_turn(drawn['direction'], drawn['lane'], rng)

        vehicles.append({
            'seq': seq,
            't_offset_sec': round(t, 6),
            'direction': drawn['direction'],
            'lane': drawn['lane'],
            'vehicle_type': drawn['vehicle_type'],
            'will_turn': turn['will_turn'],
            'turn_direction': turn['turn_direction'],
            'target_turn_lane': turn['target_turn_lane'],
            # denormalised so an analyzer can slice by load without replaying
            # the timeline
            'condition': condition,
        })

        t += 1 / trafficConditions[condition]

    header = {
        'plan_id': plan_id or default_plan_id(uneven_mode, count, seed),
        'seed': seed,
        'target_vehicle_count': count,
        'uneven_mode': uneven_mode,
        'turn_probability': turnProbability,
        'traffic_conditions': dict(trafficConditions),
        'traffic_condition_interval': trafficConditionInterval,
        'schema_version': SCHEMA_VERSION,
    }

    return {
        'header': header,
        'condition_timeline': timeline,
        'vehicles': vehicles,
    }


def default_plan_id(uneven_mode, count, seed):
    return f"{uneven_mode}_{count}_seed{seed:02d}"


def content_hash(plan):
    """
    Hash of everything a replay actually depends on.

    `created_at` and `git_rev` are provenance, not content, and are excluded
    so that regenerating a plan from the same seed produces the same hash.
    This is the determinism guarantee: same seed + count + mode + config =>
    identical hash, and identical bytes apart from those two fields.
    """
    body = {
        'header': {
            k: v for k, v in plan['header'].items()
            if k not in ('created_at', 'git_rev', 'content_hash')
        },
        'condition_timeline': plan['condition_timeline'],
        'vehicles': plan['vehicles'],
    }
    blob = json.dumps(body, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


# --- Plan I/O ------------------------------------------------------------

def load_plan(path):
    """Read a plan file and check its schema before anything else touches it."""
    with open(path) as f:
        plan = json.load(f)

    header = plan.get('header') or {}
    version = header.get('schema_version')
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Plan {path} has schema_version {version!r}, "
            f"this build understands {SCHEMA_VERSION}. Regenerate the plan."
        )

    for key in ('header', 'condition_timeline', 'vehicles'):
        if key not in plan:
            raise ValueError(f"Plan {path} is missing the '{key}' section.")

    n = header.get('target_vehicle_count')
    if n is None or len(plan['vehicles']) != n:
        raise ValueError(
            f"Plan {path} declares {n} vehicles but holds "
            f"{len(plan['vehicles'])}."
        )

    stored = header.get('content_hash')
    actual = content_hash(plan)
    if stored is not None and stored != actual:
        raise ValueError(
            f"Plan {path} has been modified since it was written "
            f"(content_hash {stored} != {actual})."
        )

    return plan


def check_plan_against_config(plan):
    """
    Return a list of reasons this plan cannot be validly replayed against the
    current config.

    A plan replayed under a different turn probability or a different arrival
    rate table is not the traffic it says it is, and the comparison it feeds
    would be silently invalid.  Caller decides whether to warn or abort.
    """
    header = plan['header']
    problems = []

    if header.get('turn_probability') != turnProbability:
        problems.append(
            f"turn_probability: plan={header.get('turn_probability')} "
            f"config={turnProbability}"
        )

    if header.get('traffic_conditions') != dict(trafficConditions):
        problems.append(
            f"traffic_conditions: plan={header.get('traffic_conditions')} "
            f"config={dict(trafficConditions)}"
        )

    if header.get('traffic_condition_interval') != trafficConditionInterval:
        problems.append(
            f"traffic_condition_interval: "
            f"plan={header.get('traffic_condition_interval')} "
            f"config={trafficConditionInterval}"
        )

    return problems


def write_plan(plan, path):
    """Write a plan, stamping provenance and the content hash into the header."""
    from datetime import datetime

    plan['header']['content_hash'] = content_hash(plan)
    plan['header']['git_rev'] = git_rev()
    plan['header']['created_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, mode="w") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")

    return path
