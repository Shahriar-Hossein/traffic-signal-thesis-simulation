"""
Summarize vehicle-count runs (state.run_mode == 'vehicles').

Reads data/logs_by_count/**, writes data/summary_count_logs/count_simulation_summary.csv.
Deliberately separate from analyze_log.py, which owns data/logs/** (time runs).
Runs that ended on the safety timeout are reported but excluded from the
pooled statistics — they are truncated, not complete.
"""

import os
import csv
import json
from datetime import datetime
from collections import defaultdict

BASE_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
LOG_ROOT = os.path.join(BASE_DIR, "logs_by_count")
SUMMARY_DIR = os.path.join(BASE_DIR, "summary_count_logs")
os.makedirs(SUMMARY_DIR, exist_ok=True)


def read_log_file(filepath):
    with open(filepath, mode='r') as f:
        return list(csv.DictReader(f))


def read_meta(filepath):
    """Load the run's metadata sidecar, if it was written."""
    meta_path = filepath.replace(".csv", "_meta.json")
    if not os.path.exists(meta_path):
        return {}
    try:
        with open(meta_path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: could not read {os.path.basename(meta_path)}: {e}")
        return {}


def analyze_count_logs():
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
        'total_duration_sec': 0.0,
        'duration_count': 0,
        'log_file_count': 0,
    })

    file_summary_count = defaultdict(int)
    incomplete = []   # runs that did not log the full target
    timed_out = []    # runs excluded from the pooled stats

    for root, _, files in os.walk(LOG_ROOT):
        # root: logs_by_count/{uneven_mode}/{target_count}
        parts = root.split(os.sep)
        uneven_mode = parts[-2] if len(parts) >= 2 else "unknown"
        count_folder = parts[-1] if len(parts) >= 1 else "unknown"

        for filename in files:
            if not filename.endswith(".csv") or "signal" in filename:
                continue

            filepath = os.path.join(root, filename)
            records = read_log_file(filepath)
            meta = read_meta(filepath)

            mode_part = filename.split("_")[0]
            label = f"{mode_part}_{uneven_mode}_n{count_folder}"

            stop_reason = meta.get('stop_reason')
            target = meta.get('target_vehicle_count')
            if target is None:
                try:
                    target = int(count_folder)
                except ValueError:
                    target = None

            # Completeness check: a full run logs exactly `target` crossings
            if target is not None and len(records) != target:
                incomplete.append((filename, len(records), target, stop_reason))

            # Truncated runs are reported but never averaged in
            if stop_reason == 'timeout':
                timed_out.append((filename, len(records), target))
                continue

            data = summary[label]
            data['log_file_count'] += 1
            file_summary_count[label] += 1

            if meta.get('duration_sec') is not None:
                data['total_duration_sec'] += float(meta['duration_sec'])
                data['duration_count'] += 1

            for r in records:
                data['total_vehicles'] += 1
                data['vehicles_by_type'][r['vehicle_type']] += 1
                data['vehicles_by_direction'][r['direction']] += 1

                try:
                    wait_time = float(r.get('wait_time_sec', 0))
                except (TypeError, ValueError) as e:
                    print(f"Warning: bad wait_time_sec {r.get('wait_time_sec')}: {e}")
                    continue

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

    # Write summary CSV
    output_file = os.path.join(SUMMARY_DIR, "count_simulation_summary.csv")
    with open(output_file, mode='w', newline='') as f:
        fieldnames = [
            "label",
            "total_vehicles",
            "log_file_count",
            "average_vehicles_per_run",
            "average_duration_sec",
            "average_throughput_vehicles_per_sec",
            "average_wait_time_sec",
            "min_wait_time_sec",
            "max_wait_time_sec",
            "average_wait_time_by_direction",
            "average_wait_time_by_type",
            "vehicles_by_type",
            "vehicles_by_direction",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for label, data in summary.items():
            runs = data['log_file_count']
            avg_wait = (
                data['total_wait_time'] / data['wait_time_counts']
                if data['wait_time_counts'] else 0
            )
            avg_duration = (
                data['total_duration_sec'] / data['duration_count']
                if data['duration_count'] else 0
            )
            avg_vehicles = data['total_vehicles'] / runs if runs else 0
            # Throughput is the meaningful cross-arm comparison here: the
            # vehicle count is fixed, so a faster run means a better controller.
            throughput = avg_vehicles / avg_duration if avg_duration else 0

            avg_wait_dir = {
                d: round(s['total'] / s['count'], 2) if s['count'] else 0
                for d, s in data['wait_time_by_direction'].items()
            }
            avg_wait_type = {
                t: round(s['total'] / s['count'], 2) if s['count'] else 0
                for t, s in data['wait_time_by_type'].items()
            }

            writer.writerow({
                "label": label,
                "total_vehicles": data['total_vehicles'],
                "log_file_count": runs,
                "average_vehicles_per_run": round(avg_vehicles, 2),
                "average_duration_sec": round(avg_duration, 2),
                "average_throughput_vehicles_per_sec": round(throughput, 3),
                "average_wait_time_sec": round(avg_wait, 2),
                "min_wait_time_sec": (
                    round(data['min_wait_time'], 2)
                    if data['min_wait_time'] != float('inf') else 0
                ),
                "max_wait_time_sec": (
                    round(data['max_wait_time'], 2)
                    if data['max_wait_time'] != float('-inf') else 0
                ),
                "average_wait_time_by_direction": str(avg_wait_dir),
                "average_wait_time_by_type": str(avg_wait_type),
                "vehicles_by_type": str(dict(data['vehicles_by_type'])),
                "vehicles_by_direction": str(dict(data['vehicles_by_direction'])),
            })

    print(f"✅ Count-mode summary saved to: {output_file}\n")

    print("🧾 Log files counted per label:")
    for label, count in file_summary_count.items():
        print(f" - {label}: {count} file(s)")

    if timed_out:
        print("\n⛔ EXCLUDED — run hit the safety timeout (truncated, not complete):")
        for filename, logged, target in timed_out:
            print(f" - {filename}: {logged}/{target} vehicles logged")

    if incomplete:
        print("\n⚠️  INCOMPLETE — logged row count != target vehicle count:")
        for filename, logged, target, reason in incomplete:
            print(f" - {filename}: {logged}/{target} rows (stop_reason={reason})")
    else:
        print("\n✅ All runs logged their full vehicle target.")


if __name__ == "__main__":
    analyze_count_logs()
