# logger.py

import csv
import json
import os
from datetime import datetime
import state

log_filename = None
signal_log_filename = None
run_basename = None


# Base folder for all data
BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def init_logger(duration_sec, uneven_mode=None):
    """
    Initialize the timestamped log files for this run.

    The destination depends on how the run ends (state.run_mode), and the two
    modes never share a folder — analyzers rebuild a run's identity from its
    folder path, so mixing them would silently pool unrelated runs.

    time mode:     data/logs/{uneven_mode}/{duration}/{mode}_log_{duration}_{ts}.csv
    vehicles mode: data/logs_by_count/{uneven_mode}/{N}/{mode}_countlog_{N}_{ts}.csv
    """
    global log_filename, signal_log_filename, run_basename

    mode_label = state.currentMode  # e.g., 'priority', 'fixed'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if state.run_mode == 'vehicles':
        bucket = str(state.target_vehicle_count)
        log_root = "logs_by_count"
        signal_root = "log_signals_by_count"
        run_basename = f"{mode_label}_countlog_{bucket}_{timestamp}"
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
    with open(log_filename, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            "timestamp",
            "vehicle_id",
            "vehicle_type",
            "direction",
            "mode",
            "wait_time_sec"
        ])

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
    meta.update(fields)

    with open(meta_path, mode="w") as file:
        json.dump(meta, file, indent=2)

    return meta_path
