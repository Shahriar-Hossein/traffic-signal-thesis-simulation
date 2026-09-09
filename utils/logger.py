# logger.py

import csv
import json
import os
from datetime import datetime
import state

log_filename = None
signal_log_filename = None
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
]


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
    global log_filename, signal_log_filename, run_basename, run_provenance

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

        log_dir = os.path.join(BASE_DATA_DIR, "paired", state.pair_id, arm)
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
