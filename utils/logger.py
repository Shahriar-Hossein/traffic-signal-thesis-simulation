# logger.py

import csv
import json
import os
import threading
from datetime import datetime
import state

log_filename = None
signal_log_filename = None
phase_log_filename = None
run_basename = None
run_provenance = None


# Base folder for all data
BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Vehicle rows carry crossing delay and the plan sequence used for pairing.
VEHICLE_LOG_COLUMNS = [
    "timestamp",
    "vehicle_id",
    "vehicle_type",
    "direction",
    "mode",
    "wait_time_sec",
]

PAIRED_EXTRA_COLUMNS = [
    "plan_seq", "lane", "will_turn", "turn_direction", "target_turn_lane",
    "released_sec", "crossed_sec",
]

# Each served green records the controller decision and whether shutdown censored it.
PHASE_LOG_COLUMNS = [
    "round_index", "phase_index", "direction", "green_start_sec",
    "green_selected_sec", "green_end_sec", "phase_end_sec",
    "decision_weight", "decision_counts", "queue_counts",
    "status", "termination",
    "lane_observations_start", "lane_observations_end",
]

# Phase statuses.  A reader that does not recognise a status must treat the
# record as unusable rather than as complete.
PHASE_COMPLETE = "complete"
PHASE_CENSORED = "censored"

# The phase currently being served, and the lock that makes writing it a
# once-only operation.  The controller runs on a daemon thread and shutdown
# runs on the main thread; without this, the run either loses its final phase
# (the thread is killed before it writes) or writes it twice.
_phase_lock = threading.Lock()
_active_phase = None


def init_logger():
    """Create one set of logs for a planned paired arm."""
    global log_filename, signal_log_filename, phase_log_filename
    global run_basename, run_provenance, _active_phase

    import config
    from core.plan import content_hash
    from core.provenance import capture_provenance
    run_provenance = capture_provenance(config, state.count_mode_timeout)
    run_provenance['plan_hash'] = content_hash(state.vehicle_plan)

    arm = state.arm_label
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_basename = f"{arm}_pairlog_{state.target_vehicle_count}_{timestamp}"
    paired_root = state.paired_root or os.path.join(BASE_DATA_DIR, "study")
    log_dir = os.path.join(paired_root, state.pair_id, arm)
    os.makedirs(log_dir, exist_ok=True)

    log_filename = os.path.join(log_dir, f"{run_basename}.csv")
    signal_log_filename = os.path.join(log_dir, f"{run_basename}_signal.csv")
    phase_log_filename = os.path.join(log_dir, f"{run_basename}_phases.csv")
    with _phase_lock:
        _active_phase = None
    with open(phase_log_filename, mode="w", newline="") as file:
        csv.writer(file).writerow(PHASE_LOG_COLUMNS)
    with open(log_filename, mode="w", newline="") as file:
        csv.writer(file).writerow(VEHICLE_LOG_COLUMNS + PAIRED_EXTRA_COLUMNS)


def log_vehicle(vehicle):
    """
    Write a single vehicle crossing record.
    """
    global log_filename
    timestamp = datetime.now()
    wait_time = vehicle.actual_wait_time
    log_entry = [
        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        id(vehicle),
        vehicle.vehicleClass,
        vehicle.direction,
        state.currentMode,
        round(wait_time, 2)
    ]

    log_entry.extend([
        vehicle.plan_seq, vehicle.lane, vehicle.will_turn,
        vehicle.turn_direction, vehicle.target_turn_lane,
        round(vehicle.released_sec, 4) if vehicle.released_sec is not None else None,
        round(vehicle.crossed_sec, 4) if vehicle.crossed_sec is not None else None,
    ])

    with open(log_filename, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(log_entry)


def log_signal_change(green_direction):
    """
    Log the time a signal turned green for a specific direction.
    """
    global signal_log_filename

    if not os.path.exists(signal_log_filename):
        with open(signal_log_filename, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "direction"])

    with open(signal_log_filename, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            green_direction
        ])


def begin_phase(**fields):
    """
    Open the record for the green that is about to be served.

    Called *before* the green is exposed, so the decision that authorised it
    exists on disk-bound state from the moment it takes effect.  Nothing is
    written yet: the row is completed by `complete_phase`, or censored by
    `finalize_phase` if the run ends first.
    """
    global _active_phase
    if not phase_log_filename:
        return
    with _phase_lock:
        _active_phase = dict(fields)


def mark_green_end(green_end_sec, termination, **fields):
    """Note when and why the green ended, while the phase is still open."""
    with _phase_lock:
        if _active_phase is not None:
            _active_phase.update(fields)
            _active_phase["green_end_sec"] = green_end_sec
            _active_phase["termination"] = termination


def complete_phase(phase_end_sec, **fields):
    """Write the open phase as a completed record and close it."""
    return _close_phase(phase_end_sec, PHASE_COMPLETE, **fields)


def finalize_phase(phase_end_sec):
    """
    Write whatever phase was still open when the run ended.

    Called once from the shutdown path on the main thread.  The controller
    thread is a daemon and is killed where it stands, so without this the
    phase that served the last vehicles simply disappears from the log.  The
    record is marked censored: its green may have been cut short, and a
    duration computed from it is not a granted duration.
    """
    return _close_phase(phase_end_sec, PHASE_CENSORED)


def _close_phase(phase_end_sec, status, **extra_fields):
    global _active_phase
    with _phase_lock:
        fields = _active_phase
        _active_phase = None
    if fields is None:
        return None
    fields.update(extra_fields)
    fields["phase_end_sec"] = phase_end_sec
    fields["status"] = status
    if status == PHASE_CENSORED:
        fields["termination"] = "shutdown"
        if fields.get("lane_observations_end") is None:
            from core.observations import capture_lane_observations
            fields["lane_observations_end"] = capture_lane_observations(
                fields["direction"], phase_end_sec)
        # The green never ended on its own terms; the run end is the only
        # bound on it that was actually observed.
        if fields.get("green_end_sec") is None:
            fields["green_end_sec"] = phase_end_sec
    log_phase(**fields)
    return fields


def log_phase(**fields):
    """Record one served green. No-op outside paired runs."""
    if not phase_log_filename:
        return

    row = dict.fromkeys(PHASE_LOG_COLUMNS)
    row.update(fields)
    for key in ("decision_counts", "queue_counts",
                "lane_observations_start", "lane_observations_end"):
        if isinstance(row[key], dict):
            row[key] = json.dumps(row[key], sort_keys=True)
    for key in ("green_start_sec", "green_end_sec", "phase_end_sec", "decision_weight"):
        if isinstance(row[key], float):
            row[key] = round(row[key], 4)

    with open(phase_log_filename, mode="a", newline="") as file:
        csv.writer(file).writerow([row[key] for key in PHASE_LOG_COLUMNS])


def write_run_meta(**fields):
    """Write the arm metadata beside its vehicle log."""
    if log_filename is None:
        return None

    meta_path = os.path.join(
        os.path.dirname(log_filename), f"{run_basename}_meta.json"
    )
    meta = {
        "run_mode": "vehicles",
        "controller": state.currentMode,
        "uneven_mode": state.uneven_mode,
        "vehicle_log": os.path.basename(log_filename),
        "signal_log": os.path.basename(signal_log_filename),
    }
    meta["phase_log"] = os.path.basename(phase_log_filename)

    meta.update(run_provenance or {})
    released = state.release_count
    meta.update({
        "generation_source": "plan",
        "plan_id": state.pair_id,
        "plan_path": state.vehicle_plan_path,
        "arm": state.arm_label,
        "vehicles_planned": state.target_vehicle_count,
        "vehicles_released": released,
        "release_drift_mean_ms": (
            round(state.release_drift_sum_ms / released, 2) if released else None
        ),
        "release_drift_max_ms": round(state.release_drift_max_ms, 2),
    })

    meta.update(fields)

    with open(meta_path, mode="w") as file:
        json.dump(meta, file, indent=2)

    return meta_path
