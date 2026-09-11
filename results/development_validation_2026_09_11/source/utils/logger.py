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

# The six columns every run has logged since the beginning.  Existing
# analyzers parse them positionally, so nothing may be inserted into this list.
VEHICLE_LOG_COLUMNS = [
    "timestamp",
    "vehicle_id",
    "vehicle_type",
    "direction",
    "mode",
    "wait_time_sec",
]

# Paired runs append identity and planned-attribute columns. Appending means
# the first six still parse positionally if a paired file ever ends up in front
# of an older analyzer — it should not, but it is cheap insurance.
PAIRED_EXTRA_COLUMNS = [
    "plan_seq", "lane", "will_turn", "turn_direction", "target_turn_lane",
    "released_sec", "crossed_sec",
]

# One row per served green, written only for paired runs so the existing
# signal-log analyzer keeps the schema it expects. This is what makes a
# controller's decisions reconstructable after the fact.
#
# `status` and `termination` are appended rather than inserted: a phase whose
# green was cut short by shutdown is a *censored* record, not a short green,
# and a report that cannot tell the two apart deletes exactly the phase that
# completed the workload.
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


def is_paired_run():
    """A run is 'paired' exactly when the driver gave it a pair identity."""
    return state.pair_id is not None


def init_logger(duration_sec, uneven_mode=None):
    """
    Initialize the timestamped log files for this run.

    The destination depends on how the run ends (state.run_mode) and on whether
    this is one arm of a paired replay.  The roots never share a folder —
    analyzers rebuild a run's identity from its folder path, so mixing them
    would silently pool unrelated runs.

    time mode:     data/logs/{uneven_mode}/{duration}/{mode}_log_{duration}_{ts}.csv
    vehicles mode: data/logs_by_count/{uneven_mode}/{N}/{mode}_countlog_{N}_{ts}.csv
    paired replay: data/paired/{pair_id}/{arm}/{arm}_pairlog_{N}_{ts}.csv
    """
    global log_filename, signal_log_filename, phase_log_filename
    global run_basename, run_provenance

    if is_paired_run():
        import config
        from core.plan import content_hash
        from core.provenance import capture_provenance
        run_provenance = capture_provenance(config, state.count_mode_timeout)
        run_provenance['plan_hash'] = content_hash(state.vehicle_plan)

    mode_label = state.currentMode  # e.g., 'priority', 'fixed'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if is_paired_run():
        # A third root, sibling to logs/ and logs_by_count/, for the same
        # reason count mode got its own: a paired run does not fit the shape
        # either existing analyzer expects, and no existing analyzer walks
        # data/paired, so nothing it writes can contaminate a summary.
        bucket = str(state.target_vehicle_count)
        arm = state.arm_label or mode_label
        run_basename = f"{arm}_pairlog_{bucket}_{timestamp}"

        paired_root = getattr(state, 'paired_root', None)
        if paired_root is None:
            paired_root = os.path.join(BASE_DATA_DIR, "paired")
        log_dir = os.path.join(paired_root, state.pair_id, arm)
        signal_dir = log_dir  # both arms' logs live together in the arm folder
    elif state.run_mode == 'vehicles':
        bucket = str(state.target_vehicle_count)
        log_root = "logs_by_count"
        signal_root = "log_signals_by_count"
        run_basename = f"{mode_label}_countlog_{bucket}_{timestamp}"
        log_dir = os.path.join(BASE_DATA_DIR, log_root, uneven_mode, bucket)
        signal_dir = os.path.join(BASE_DATA_DIR, signal_root, uneven_mode, bucket)
    else:
        bucket = str(duration_sec)  # just seconds as folder name
        log_root = "logs"
        signal_root = "log_signals"
        run_basename = f"{mode_label}_log_{bucket}_{timestamp}"
        log_dir = os.path.join(BASE_DATA_DIR, log_root, uneven_mode, bucket)
        signal_dir = os.path.join(BASE_DATA_DIR, signal_root, uneven_mode, bucket)

    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(signal_dir, exist_ok=True)

    log_filename = os.path.join(log_dir, f"{run_basename}.csv")
    signal_log_filename = os.path.join(signal_dir, f"{run_basename}_signal.csv")
    phase_log_filename = (
        os.path.join(log_dir, f"{run_basename}_phases.csv")
        if is_paired_run() else None
    )
    if phase_log_filename:
        with _phase_lock:
            global _active_phase
            _active_phase = None
        with open(phase_log_filename, mode="w", newline="") as file:
            csv.writer(file).writerow(PHASE_LOG_COLUMNS)

    # Write CSV headers
    columns = list(VEHICLE_LOG_COLUMNS)
    if is_paired_run():
        columns += PAIRED_EXTRA_COLUMNS

    with open(log_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)

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

    if is_paired_run():
        # The pairing key.  id(vehicle) cannot serve as one — CPython reuses
        # addresses after a despawn, so joining the two arms on it would
        # silently mismatch vehicles.
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
    """
    Write a per-run metadata sidecar next to the vehicle log.

    JSON is used deliberately: every analyzer filters on '.csv', so a sidecar
    can never contaminate an existing summary.
    """
    if log_filename is None:
        return None

    meta_path = os.path.join(
        os.path.dirname(log_filename), f"{run_basename}_meta.json"
    )
    meta = {
        "run_mode": state.run_mode,
        "controller": state.currentMode,
        "uneven_mode": state.uneven_mode,
        "vehicle_log": os.path.basename(log_filename),
        "signal_log": os.path.basename(signal_log_filename),
    }
    if phase_log_filename:
        meta["phase_log"] = os.path.basename(phase_log_filename)

    if is_paired_run():
        # The folder path stops being the only run metadata here: a paired
        # run records its own identity and its adherence to the plan, which
        # is what the validity gate reads.
        meta.update(run_provenance or {})
        released = state.release_count
        meta.update({
            "generation_source": state.generation_source,
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
