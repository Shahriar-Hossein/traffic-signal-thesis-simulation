import os
import csv
from datetime import datetime
from collections import defaultdict

LOG_DIR = "logs"
SUMMARY_DIR = "summary_logs"
os.makedirs(SUMMARY_DIR, exist_ok=True)

def read_log_file(filepath):
    """
    Reads a single log CSV and returns list of dict records.
    Assumes columns: timestamp, vehicle_id, vehicle_type, direction, mode, wait_time_sec
    """
    records = []
    with open(filepath, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def analyze_logs():
    """
    Analyze all log files and produce summary statistics per mode.
    """

    # Data structures to accumulate info
    summary = defaultdict(lambda: {
        'total_vehicles': 0,
        'vehicles_by_type': defaultdict(int),
        'vehicles_by_direction': defaultdict(int),
        'total_wait_time': 0.0,
        'wait_time_counts': 0,
        'wait_time_by_direction': defaultdict(lambda: {'total': 0.0, 'count': 0}),
        'wait_time_by_type': defaultdict(lambda: {'total': 0.0, 'count': 0}),
        'timestamps': [],
        'vehicle_ids': set(),
    })

    for filename in os.listdir(LOG_DIR):
        if not filename.endswith(".csv"):
            continue
        filepath = os.path.join(LOG_DIR, filename)
        print(f"Processing {filename}...")
        records = read_log_file(filepath)

        for r in records:
            mode = r['mode']
            summary_data = summary[mode]

            summary_data['total_vehicles'] += 1
            summary_data['vehicles_by_type'][r['vehicle_type']] += 1
            summary_data['vehicles_by_direction'][r['direction']] += 1
            summary_data['vehicle_ids'].add(r['vehicle_id'])

            # Parse timestamp string to datetime
            try:
                ts = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
                summary_data['timestamps'].append(ts)
            except Exception as e:
                print(f"Warning: could not parse timestamp {r['timestamp']}: {e}")

            # Parse and accumulate wait time
            try:
                wait_time = float(r.get('wait_time_sec', 0))
                summary_data['total_wait_time'] += wait_time
                summary_data['wait_time_counts'] += 1

                # By direction
                dir_stats = summary_data['wait_time_by_direction'][r['direction']]
                dir_stats['total'] += wait_time
                dir_stats['count'] += 1

                # By vehicle type
                type_stats = summary_data['wait_time_by_type'][r['vehicle_type']]
                type_stats['total'] += wait_time
                type_stats['count'] += 1

            except Exception as e:
                print(f"Warning: could not parse wait_time_sec {r.get('wait_time_sec')}: {e}")

    # Now prepare the output summary CSV

    output_file = os.path.join(SUMMARY_DIR, "simulation_summary.csv")
    with open(output_file, mode='w', newline='') as f:
        fieldnames = [
            "mode",
            "total_vehicles",
            "unique_vehicles",
            "time_span_seconds",
            "average_wait_time_sec",
            "average_wait_time_by_direction",
            "average_wait_time_by_type",
            "vehicles_by_type",
            "vehicles_by_direction"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for mode, data in summary.items():
            timestamps = data['timestamps']
            if timestamps:
                time_span = (max(timestamps) - min(timestamps)).total_seconds()
            else:
                time_span = 0

            avg_wait = (data['total_wait_time'] / data['wait_time_counts']) if data['wait_time_counts'] > 0 else 0

            avg_wait_dir = {
                d: (stats['total'] / stats['count']) if stats['count'] > 0 else 0
                for d, stats in data['wait_time_by_direction'].items()
            }
            avg_wait_type = {
                t: (stats['total'] / stats['count']) if stats['count'] > 0 else 0
                for t, stats in data['wait_time_by_type'].items()
            }

            row = {
                "mode": mode,
                "total_vehicles": data['total_vehicles'],
                "unique_vehicles": len(data['vehicle_ids']),
                "time_span_seconds": round(time_span, 2),
                "average_wait_time_sec": round(avg_wait, 2),
                "average_wait_time_by_direction": str({k: round(v, 2) for k, v in avg_wait_dir.items()}),
                "average_wait_time_by_type": str({k: round(v, 2) for k, v in avg_wait_type.items()}),
                "vehicles_by_type": str(dict(data['vehicles_by_type'])),
                "vehicles_by_direction": str(dict(data['vehicles_by_direction'])),
            }

            writer.writerow(row)

    print(f"Summary saved to {output_file}")

if __name__ == "__main__":
    analyze_logs()
