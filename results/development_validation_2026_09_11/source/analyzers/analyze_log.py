import os
import csv
from datetime import datetime
from collections import defaultdict

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LOG_ROOT = os.path.join(BASE_DIR, "logs")
SUMMARY_DIR = os.path.join(BASE_DIR, "summary_logs")
os.makedirs(SUMMARY_DIR, exist_ok=True)

def read_log_file(filepath):
    records = []
    with open(filepath, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def analyze_logs():
    summary = defaultdict(lambda: {
        'total_vehicles': 0,
        'vehicles_by_type': defaultdict(int),
        'vehicles_by_direction': defaultdict(int),
        'total_wait_time': 0.0,
        'wait_time_counts': 0,
        'wait_time_by_direction': defaultdict(lambda: {'total': 0.0, 'count': 0}),
        'wait_time_by_type': defaultdict(lambda: {'total': 0.0, 'count': 0}),
        'min_wait_time': float('inf'),
        'max_wait_time': float('-inf'),
        'timestamps': [],
        'vehicle_ids': set(),
        'log_file_count': 0
    })

    file_summary_count = defaultdict(int)

    for root, _, files in os.walk(LOG_ROOT):
        # root: logs/top_right/120
        parts = root.split(os.sep)
        # parts[-1] = '120' (duration)
        # parts[-2] = 'top_right' (uneven mode)
        uneven_mode = parts[-2] if len(parts) >= 2 else "unknown"
        duration_folder = parts[-1] if len(parts) >= 1 else "unknown"
        
        for filename in files:
            if not filename.endswith(".csv"):
                continue

            filepath = os.path.join(root, filename)
            records = read_log_file(filepath)

            # folder = os.path.basename(root)
            mode_part = filename.split("_")[0]
            label = f"{mode_part}_{uneven_mode}_{duration_folder}"

            data = summary[label]
            data['log_file_count'] += 1
            file_summary_count[label] += 1

            for r in records:
                data['total_vehicles'] += 1
                data['vehicles_by_type'][r['vehicle_type']] += 1
                data['vehicles_by_direction'][r['direction']] += 1
                data['vehicle_ids'].add(r['vehicle_id'])

                try:
                    ts = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
                    data['timestamps'].append(ts)
                except Exception as e:
                    print(f"Warning: could not parse timestamp {r['timestamp']}: {e}")

                try:
                    wait_time = float(r.get('wait_time_sec', 0))
                    data['total_wait_time'] += wait_time
                    data['wait_time_counts'] += 1
                    data['min_wait_time'] = min(data['min_wait_time'], wait_time)
                    data['max_wait_time'] = max(data['max_wait_time'], wait_time)

                    dir_stats = data['wait_time_by_direction'][r['direction']]
                    dir_stats['total'] += wait_time
                    dir_stats['count'] += 1

                    type_stats = data['wait_time_by_type'][r['vehicle_type']]
                    type_stats['total'] += wait_time
                    type_stats['count'] += 1

                except Exception as e:
                    print(f"Warning: could not parse wait_time_sec {r.get('wait_time_sec')}: {e}")

    # Write summary CSV
    output_file = os.path.join(SUMMARY_DIR, "simulation_summary.csv")
    with open(output_file, mode='w', newline='') as f:
        fieldnames = [
            "label",
            "total_vehicles",
            "unique_vehicles",
            "log_file_count",
            "average_wait_time_sec",
            "min_wait_time_sec",
            "max_wait_time_sec",
            "average_throughput_vehicles_per_file",
            "average_wait_time_by_direction",
            "average_wait_time_by_type",
            "vehicles_by_type",
            "vehicles_by_direction"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for label, data in summary.items():
            avg_wait = data['total_wait_time'] / data['wait_time_counts'] if data['wait_time_counts'] else 0
            avg_throughput = data['total_vehicles'] / data['log_file_count'] if data['log_file_count'] else 0

            avg_wait_dir = {
                d: round(stats['total'] / stats['count'], 2) if stats['count'] > 0 else 0
                for d, stats in data['wait_time_by_direction'].items()
            }
            avg_wait_type = {
                t: round(stats['total'] / stats['count'], 2) if stats['count'] > 0 else 0
                for t, stats in data['wait_time_by_type'].items()
            }

            row = {
                "label": label,
                "total_vehicles": data['total_vehicles'],
                "unique_vehicles": len(data['vehicle_ids']),
                "log_file_count": data['log_file_count'],
                "average_wait_time_sec": round(avg_wait, 2),
                "min_wait_time_sec": round(data['min_wait_time'], 2) if data['min_wait_time'] != float('inf') else 0,
                "max_wait_time_sec": round(data['max_wait_time'], 2) if data['max_wait_time'] != float('-inf') else 0,
                "average_throughput_vehicles_per_file": round(avg_throughput, 2),
                "average_wait_time_by_direction": str(avg_wait_dir),
                "average_wait_time_by_type": str(avg_wait_type),
                "vehicles_by_type": str(dict(data['vehicles_by_type'])),
                "vehicles_by_direction": str(dict(data['vehicles_by_direction']))
            }

            writer.writerow(row)

    print(f"✅ Summary saved to: {output_file}\n")

    # Print how many files were summarized per group
    print("🧾 Log files counted per label:")
    for label, count in file_summary_count.items():
        print(f" - {label}: {count} file(s)")

if __name__ == "__main__":
    analyze_logs()
