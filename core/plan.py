"""Build and validate immutable, scheduled traffic plans for paired replay."""

import hashlib
import json
import math
import os
import random
import subprocess

from config import (
    directionNumbers, vehicleTypes,
    trafficConditions,
    turnDirections, turnProbability,
)

# Bumped whenever the plan file's shape changes.  A plan whose version this
# code does not know is rejected loudly rather than half-read.
SCHEMA_VERSION = 2

# Same order as config.directionNumbers — the direction weight lists below are
# positional against it.
DIRECTIONS = list(directionNumbers.values())

# Lanes a vehicle can be generated into; lane 3 remains in the render tables.
LANE_COUNT = 3

# build_plan stores cumulative virtual-clock offsets rounded independently to
# six decimal places.  Two adjacent stored values can therefore differ from
# the unrounded interval by one whole unit in the last stored place.
ARRIVAL_OFFSET_DECIMALS = 6

# Direction probabilities for the three study patterns.
DIRECTION_WEIGHTS = {
    'right': [0.85, 0.05, 0.05, 0.05],
    'up_down': [0.15, 0.35, 0.15, 0.35],
}

UNIFORM_WEIGHTS = [0.25, 0.25, 0.25, 0.25]


UNIFORM_MODES = ('even',)


def direction_weights(uneven_mode):
    """Return the probability vector for a study demand pattern."""
    if uneven_mode in UNIFORM_MODES:
        return UNIFORM_WEIGHTS
    try:
        return DIRECTION_WEIGHTS[uneven_mode]
    except KeyError:
        raise ValueError(
            f"unknown uneven_mode {uneven_mode!r}; expected one of "
            f"{sorted(DIRECTION_WEIGHTS)} or one of {list(UNIFORM_MODES)}"
        ) from None


def sample_vehicle(uneven_mode, rng):
    """Draw one vehicle type, direction and lane from a seeded RNG."""
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


def _scheduled_arrivals(schedule, rates):
    """Return fixed boundaries and every arrival strictly before the end."""
    if not isinstance(schedule, list) or not schedule:
        raise ValueError("schedule must be a nonempty list of condition/duration segments")
    timeline = []
    arrivals = []
    start = 0.0
    for segment in schedule:
        if not isinstance(segment, dict) or set(segment) != {'condition', 'duration_sec'}:
            raise ValueError("invalid schedule segment")
        condition, duration = segment['condition'], segment['duration_sec']
        if not isinstance(condition, str) or condition not in rates:
            raise ValueError("invalid schedule condition")
        if (type(duration) not in (int, float) or not math.isfinite(duration)
                or duration <= 0 or round(duration, ARRIVAL_OFFSET_DECIMALS) != duration):
            raise ValueError("schedule duration_sec must be positive and representable to six decimals")
        end = round(start + duration, ARRIVAL_OFFSET_DECIMALS)
        if end <= start:
            raise ValueError("schedule duration_sec is too small")
        timeline.append({'t_offset_sec': start, 'condition': condition})
        index = 0
        while True:
            offset = round(start + index / rates[condition], ARRIVAL_OFFSET_DECIMALS)
            if offset >= end:
                break
            if arrivals and offset <= arrivals[-1][0]:
                raise ValueError("schedule arrival resolution is insufficient")
            arrivals.append((offset, condition))
            index += 1
        start = end
    return timeline, arrivals, start


def build_plan(seed, uneven_mode, schedule, plan_id=None, scenario=None):
    """Generate all arrivals for each fixed-duration segment."""
    if scenario is not None and (not isinstance(scenario, str) or not scenario):
        raise ValueError("scenario must be a nonempty string")
    direction_weights(uneven_mode)
    timeline, arrivals, _ = _scheduled_arrivals(schedule, trafficConditions)
    rng = random.Random(seed)
    vehicles = []
    for seq, (offset, current_condition) in enumerate(arrivals):
        drawn = sample_vehicle(uneven_mode, rng)
        turn = sample_turn(drawn['direction'], drawn['lane'], rng)
        vehicles.append({
            'seq': seq, 't_offset_sec': offset,
            'direction': drawn['direction'], 'lane': drawn['lane'],
            'vehicle_type': drawn['vehicle_type'],
            'will_turn': turn['will_turn'],
            'turn_direction': turn['turn_direction'],
            'target_turn_lane': turn['target_turn_lane'],
            'condition': current_condition,
        })
    schedule_copy = [dict(segment) for segment in schedule]
    schedule_hash = hashlib.sha256(json.dumps(
        {'schedule': schedule_copy, 'scenario': scenario}, sort_keys=True
    ).encode()).hexdigest()[:8]
    header = {
        'plan_id': plan_id or f"{uneven_mode}_schedule_{schedule_hash}_seed{seed:02d}",
        'seed': seed, 'target_vehicle_count': len(vehicles),
        'uneven_mode': uneven_mode, 'turn_probability': turnProbability,
        'traffic_conditions': dict(trafficConditions),
        'arrival_schedule': schedule_copy, 'scenario': scenario,
        'schema_version': SCHEMA_VERSION,
    }
    return {'header': header, 'condition_timeline': timeline, 'vehicles': vehicles}


def content_hash(plan):
    """
    Hash of everything a replay actually depends on.

    `created_at` and `git_rev` are provenance, not content, and are excluded
    so that regenerating a plan from the same seed produces the same hash.
    This is the determinism guarantee: same seed + schedule + mode + config =>
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
            f"this build understands only {SCHEMA_VERSION}. Regenerate the plan."
        )

    for key in ('header', 'condition_timeline', 'vehicles'):
        if key not in plan:
            raise ValueError(f"Plan {path} is missing the '{key}' section.")

    if 'uneven_mode' not in header or (header['uneven_mode'] is not None
                                       and not isinstance(header['uneven_mode'], str)):
        raise ValueError(f"Plan {path}: missing or invalid uneven_mode.")
    # The same validator the builder uses, so a schema that promises supported
    # skews cannot accept a name the sampler would refuse.
    try:
        direction_weights(header['uneven_mode'])
    except ValueError as error:
        raise ValueError(f"Plan {path}: {error}") from None
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
    scenario = header.get('scenario')
    if scenario is not None and (not isinstance(scenario, str) or not scenario):
        raise ValueError(f"Plan {path}: invalid scenario.")
    try:
        expected_timeline, expected_arrivals, _ = _scheduled_arrivals(
            header.get('arrival_schedule'), rates)
    except ValueError as error:
        raise ValueError(f"Plan {path}: {error}") from None
    if timeline != expected_timeline:
        raise ValueError(f"Plan {path}: timeline does not match arrival_schedule.")

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

    # Reject a rehashed plan whose vehicle label contradicts its schedule.
    for record in plan['vehicles']:
        active = active_condition(timeline, record['t_offset_sec'])
        if record['condition'] != active:
            raise ValueError(
                f"Plan {path}: vehicle {record['seq']} is labelled "
                f"{record['condition']!r} but the timeline has {active!r} in "
                f"force at {record['t_offset_sec']}s."
            )

    observed = [(record['t_offset_sec'], record['condition'])
                for record in plan['vehicles']]
    if observed != expected_arrivals:
        raise ValueError(f"Plan {path}: arrivals do not match arrival_schedule.")
    return plan


def active_condition(timeline, offset):
    """The condition the timeline puts in force at `offset`."""
    condition = None
    for event in timeline:
        if event['t_offset_sec'] <= offset:
            condition = event['condition']
        else:
            break
    return condition


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
