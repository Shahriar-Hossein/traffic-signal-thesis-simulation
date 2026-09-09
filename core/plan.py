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
import math
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


# 'even' and None both mean uniform; every other name must be a real skew.
UNIFORM_MODES = (None, 'even', 'uniform')


def direction_weights(uneven_mode):
    """
    Direction probabilities for a demand skew ('even'/None -> uniform).

    An unrecognised name used to fall back to uniform, so a typo produced a
    balanced plan labelled as a skewed one — and nothing said so.
    """
    if uneven_mode in UNIFORM_MODES:
        return UNIFORM_WEIGHTS
    try:
        return DIRECTION_WEIGHTS[uneven_mode]
    except KeyError:
        raise ValueError(
            f"unknown uneven_mode {uneven_mode!r}; expected one of "
            f"{sorted(DIRECTION_WEIGHTS)} or one of {list(UNIFORM_MODES)}"
        ) from None


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


def build_plan(seed, count, uneven_mode, plan_id=None, condition=None):
    """
    Generate a full replay plan on a *virtual* clock.

    The clock advances by `1 / trafficConditions[condition]` per vehicle and
    switches condition on the `trafficConditionInterval` boundary — exactly
    what core/generator.py does against `time.time()`, minus the sleep drift.
    The drift is deliberately not modelled: it is a property of the machine on
    the day, not of the traffic, and both replay arms re-impose their own.

    `condition` pins one traffic condition for the whole plan instead of
    switching between them. That is what gives a scenario a single demand
    regime — below capacity, near it, or over it — rather than a mixture of
    all three. Left None, the condition switches as it always has.

    Uses a private `random.Random(seed)`; never the global module, so nothing
    else in the process can perturb the sequence.
    """
    if condition is not None and condition not in trafficConditions:
        raise ValueError(
            f"unknown traffic condition {condition!r}; "
            f"expected one of {sorted(trafficConditions)}"
        )
    rng = random.Random(seed)
    pinned = condition

    vehicles = []
    timeline = []

    t = 0.0
    condition = None
    condition_started_at = None

    for seq in range(count):
        # Mirrors generator.py: the condition is picked *before* the vehicle
        # draws, so the rng sequence lines up with the live path.
        if condition is None or t - condition_started_at >= trafficConditionInterval:
            # A pinned condition is chosen once and never drawn, so it costs
            # no rng draws and cannot shift the vehicle sequence relative to
            # an unpinned plan of the same seed.
            condition = pinned or pick_traffic_condition(condition, rng)
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
        # None means the plan switches conditions; a name means it holds that
        # one throughout. Part of the content hash, so the two are distinct
        # plans even at the same seed.
        'pinned_condition': pinned,
        'schema_version': SCHEMA_VERSION,
    }

    return {
        'header': header,
        'condition_timeline': timeline,
        'vehicles': vehicles,
    }


def default_plan_id(uneven_mode, count, seed, condition=None):
    """Folder-safe identity. The condition is part of it: two plans that
    differ only in demand regime must not collide."""
    label = f"{uneven_mode}_{count}_seed{seed:02d}"
    return label if condition is None else f"{uneven_mode}_{condition}_{count}_seed{seed:02d}"


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

    if not isinstance(plan, dict) or not isinstance(plan.get('header'), dict):
        raise ValueError(f"Plan {path} must contain a header object.")
    header = plan['header']
    version = header.get('schema_version')
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Plan {path} has schema_version {version!r}, "
            f"this build understands {SCHEMA_VERSION}. Regenerate the plan."
        )

    for key in ('header', 'condition_timeline', 'vehicles'):
        if key not in plan:
            raise ValueError(f"Plan {path} is missing the '{key}' section.")

    if 'uneven_mode' not in header or (header['uneven_mode'] is not None
                                       and not isinstance(header['uneven_mode'], str)):
        raise ValueError(f"Plan {path}: missing or invalid uneven_mode.")
    if 'pinned_condition' not in header:
        raise ValueError(f"Plan {path}: missing pinned_condition.")
    rates = header.get('traffic_conditions')
    if not isinstance(rates, dict) or not rates or any(
        not isinstance(key, str) or type(rate) not in (int, float)
        or not math.isfinite(rate) or rate <= 0 for key, rate in rates.items()
    ):
        raise ValueError(f"Plan {path}: invalid traffic_conditions.")
    timeline = plan['condition_timeline']
    if not isinstance(timeline, list) or not timeline:
        raise ValueError(f"Plan {path}: invalid condition_timeline.")
    last_offset = -1
    for event in timeline:
        if not isinstance(event, dict):
            raise ValueError(f"Plan {path}: invalid condition event.")
        offset, condition = event.get('t_offset_sec'), event.get('condition')
        if (type(offset) not in (int, float) or not math.isfinite(offset)
                or offset < 0 or offset <= last_offset
                or not isinstance(condition, str) or condition not in rates):
            raise ValueError(f"Plan {path}: invalid condition event.")
        last_offset = offset
    if timeline[0]['t_offset_sec'] != 0:
        raise ValueError(f"Plan {path}: condition timeline must start at zero.")
    pinned = header['pinned_condition']
    if pinned is not None:
        if pinned not in rates:
            raise ValueError(f"Plan {path}: unknown pinned_condition {pinned!r}.")
        if any(event['condition'] != pinned for event in timeline):
            raise ValueError(f"Plan {path}: timeline contradicts pinned_condition.")

    n = header.get('target_vehicle_count')
    if type(n) is not int or n <= 0 or not isinstance(plan['vehicles'], list) or len(plan['vehicles']) != n:
        raise ValueError(
            f"Plan {path} declares {n} vehicles but holds "
            f"an invalid vehicle list."
        )

    stored = header.get('content_hash')
    actual = content_hash(plan)
    if not stored or stored != actual:
        raise ValueError(
            f"Plan {path} has been modified since it was written "
            f"(content_hash {stored} != {actual})."
        )

    previous = -1.0
    for seq, record in enumerate(plan['vehicles']):
        if not isinstance(record, dict) or type(record.get('seq')) is not int or record['seq'] != seq:
            raise ValueError(f"Plan {path}: vehicle IDs must be exactly 0..N-1 in order.")
        offset = record.get('t_offset_sec')
        if (type(offset) not in (int, float) or not math.isfinite(offset)
                or offset < 0 or offset < previous):
            raise ValueError(f"Plan {path}: invalid arrival time at seq {seq}.")
        previous = offset
        direction, lane = record.get('direction'), record.get('lane')
        turning = record.get('will_turn')
        target = record.get('target_turn_lane')
        if (direction not in DIRECTIONS or type(lane) is not int or lane not in range(LANE_COUNT)
                or record.get('vehicle_type') not in vehicleTypes.values()
                or type(turning) is not bool or type(target) is not int
                or target not in range(LANE_COUNT)
                or not isinstance(record.get('condition'), str)
                or record['condition'] not in rates):
            raise ValueError(f"Plan {path}: invalid vehicle attributes at seq {seq}.")
        expected_turn = turnDirections[direction][lane] if turning else direction
        if (record.get('turn_direction') != expected_turn
                or (turning and expected_turn == direction) or (not turning and target != 0)):
            raise ValueError(f"Plan {path}: inconsistent turn at seq {seq}.")
    if not isinstance(header.get('plan_id'), str) or not header['plan_id']:
        raise ValueError(f"Plan {path}: missing plan_id.")
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
