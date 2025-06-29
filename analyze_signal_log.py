import os
import csv
from datetime import datetime
from collections import defaultdict

LOG_ROOT = "log_signals"
SUMMARY_DIR = "summary_signals"
os.makedirs(SUMMARY_DIR, exist_ok=True)

def read_log_file(filepath):
    records = []
    with open(filepath, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def analyze_signal_logs():
    # Store per-label info:
    # Each label contains a list of per-file averages for each direction
    summary = defaultdict(lambda: {
        'cycle_times_by_direction': defaultdict(list),  # direction => list of avg cycle times per file
        'log_file_count': 0
    })

    file_summary_count = defaultdict(int)

    for root, _, files in os.walk(LOG_ROOT):
        parts = root.split(os.sep)
        uneven_mode = parts[-2] if len(parts) >= 2 else "unknown"
        duration_folder = parts[-1] if len(parts) >= 1 else "unknown"

        for filename in files:
            if not filename.endswith(".csv") or "signal" not in filename:
                continue

            filepath = os.path.join(root, filename)
            records = read_log_file(filepath)
            print(f"Parsed {len(records)} records from {filename}")

            mode_part = filename.split("_")[0]
            label = f"{mode_part}_{uneven_mode}_{duration_folder}"

            file_summary_count[label] += 1
            summary[label]['log_file_count'] += 1

            # Collect timestamps grouped by direction **per file**
            timestamps_by_direction = defaultdict(list)

            for r in records:
                try:
                    ts = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
                    direction = r['direction']
                    timestamps_by_direction[direction].append(ts)
                except Exception as e:
                    print(f"Warning: could not parse timestamp {r['timestamp']}: {e}")

            # Calculate average cycle time per direction for this file
            for direction, timestamps in timestamps_by_direction.items():
                timestamps.sort()
                intervals = [
                    (timestamps[i+1] - timestamps[i]).total_seconds()
                    for i in range(len(timestamps) - 1)
                ]

                if intervals:
                    avg_cycle = sum(intervals) / len(intervals)
                    summary[label]['cycle_times_by_direction'][direction].append(avg_cycle)
                    print(f"[DEBUG] {label} - {direction} avg cycle in file {filename}: {avg_cycle:.2f} sec")
                else:
                    print(f"[DEBUG] {label} - {direction} has no intervals in file {filename}")

    # Now aggregate per label: average of averages for each direction
    output_file = os.path.join(SUMMARY_DIR, "signal_summary.csv")
    with open(output_file, mode='w', newline='') as f:
        fieldnames = [
            "label",
            "log_file_count",
            "average_cycle_time_by_direction"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for label, data in summary.items():
            avg_cycle_by_dir = {}
            for direction, cycles in data['cycle_times_by_direction'].items():
                avg_cycle_by_dir[direction] = round(sum(cycles) / len(cycles), 2) if cycles else 0

            row = {
                "label": label,
                "log_file_count": data['log_file_count'],
                "average_cycle_time_by_direction": str(avg_cycle_by_dir)
            }
            writer.writerow(row)

    print(f"✅ Signal summary saved to: {output_file}\n")

    print("🧾 Signal log files counted per label:")
    for label, count in file_summary_count.items():
        print(f" - {label}: {count} file(s)")

if __name__ == "__main__":
    analyze_signal_logs()
