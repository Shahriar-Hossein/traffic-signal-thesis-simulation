# logger.py

import csv
import os
from datetime import datetime
import state

# Create global log filename ONCE for this run
log_filename = None

def init_logger():
    """
    Create a timestamped log file with headers.
    """
    global log_filename
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(
        log_dir,
        f"{state.currentMode}_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

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
    timestamp = datetime.now()
    wait_time = (timestamp - vehicle.created_at).total_seconds()
    log_entry = [
        timestamp.strftime("%Y-%m-%d %H:%M:%S"), 
        id(vehicle), 
        vehicle.vehicleClass, 
        vehicle.direction, 
        state.currentMode,
        round(wait_time,2)
    ]

    with open(log_filename, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(log_entry)
