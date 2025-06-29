# logger.py

import csv
import os
from datetime import datetime
import state

log_filename = None

def init_logger(duration_sec, uneven_mode=None):
    """
    Initialize a timestamped log file inside mode and duration-based subfolders.
    Example: logs/priority/120/priority_log_120_20250622_231230.csv
    """
    global log_filename

    mode_label = state.currentMode  # e.g., 'priority', 'fixed'
    duration_label = str(duration_sec)  # just seconds as folder name

    log_dir = os.path.join("logs", uneven_mode, duration_label)
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = os.path.join(
        log_dir,
        f"{mode_label}_log_{duration_label}_{timestamp}.csv"
    )

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
    global log_filename
    signal_log_dir = log_filename.replace("logs", "log_signals").replace(".csv", "_signal.csv")
    os.makedirs(os.path.dirname(signal_log_dir), exist_ok=True)


    if not os.path.exists(signal_log_dir):
        with open(signal_log_dir, mode="w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "direction"]) 

    with open(signal_log_dir, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            green_direction
        ])