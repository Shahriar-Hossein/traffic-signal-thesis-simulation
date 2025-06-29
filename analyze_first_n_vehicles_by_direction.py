import os
import csv
from datetime import datetime
from collections import defaultdict

LOG_ROOT = "logs"
SUMMARY_DIR = "summary_first_vehicles_by_direction_algorithm"
os.makedirs(SUMMARY_DIR, exist_ok=True)

N = 10  # Number of vehicles per direction (change as needed)
DIRECTIONS = ['up', 'down', 'left', 'right']

def read_log_file(filepath):
    records = []
    with open(filepath, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(row)
    return records

def analyze_first_n_by_direction_algorithm():
    # Dictionary: {(direction, algorithm): [list of dicts]}
    summaries = defaultdict(list)

    total_files = 0
    files_with_data = 0

    for root, _, files in os.walk(LOG_ROOT):
        parts = root.split(os.sep)
        uneven_mode = parts[-2] if len(parts) >= 2 else "unknown_mode"
        duration_folder = parts[-1] if len(parts) >= 1 else "unknown_duration"

        for filename in files:
            if not filename.endswith(".csv") or "signal" in filename:
                continue

            total_files += 1
            filepath = os.path.join(root, filename)
            records = read_log_file(filepath)

            # Extract algorithm from filename prefix (before first underscore)
            algorithm = filename.split('_')[0] if '_' in filename else "unknown_algorithm"

            file_had_data = False

            for direction in DIRECTIONS:
                filtered = [r for r in records if r['direction'] == direction]
                if len(filtered) < N:
                    continue

                truncated = filtered[:N]

                # Calculate time span for the first N vehicles in this direction
                t0 = datetime.strptime(truncated[0]['timestamp'], "%Y-%m-%d %H:%M:%S")
                tN = datetime.strptime(truncated[-1]['timestamp'], "%Y-%m-%d %H:%M:%S")
                sim_duration = (tN - t0).total_seconds()

                wait_times = [float(r['wait_time_sec']) for r in truncated]
                types = [r['vehicle_type'] for r in truncated]
                type_counts = {t: types.count(t) for t in set(types)}

                label = f"{algorithm}_{uneven_mode}_{duration_folder}"

                summaries[(direction, algorithm)].append({
                    "label": label,
                    "log_file": filename,
                    "direction": direction,
                    "algorithm": algorithm,
                    "uneven_mode": uneven_mode,
                    "duration_to_pass_n_sec": round(sim_duration, 2),
                    "avg_wait_time_sec": round(sum(wait_times) / len(wait_times), 2),
                    "min_wait_time_sec": round(min(wait_times), 2),
                    "max_wait_time_sec": round(max(wait_times), 2),
                    "vehicles_by_type": str(type_counts)
                })
                file_had_data = True

            if file_had_data:
                files_with_data += 1

    if files_with_data == 0:
        print("⚠️ No data found for any direction/algorithm with at least N vehicles.")
        return

    # Write detailed CSV per (direction, algorithm)
    for (direction, algorithm), rows in summaries.items():
        output_file = os.path.join(SUMMARY_DIR, f"first_{N}_vehicles_{direction}_{algorithm}.csv")
        with open(output_file, mode='w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"✅ Detailed summary saved for direction '{direction}', algorithm '{algorithm}': {output_file}")

    # Aggregate summary for comparison
    aggregate_summary = []
    for (direction, algorithm), rows in summaries.items():
        count = len(rows)
        avg_duration = round(sum(r["duration_to_pass_n_sec"] for r in rows) / count, 2)
        avg_wait = round(sum(r["avg_wait_time_sec"] for r in rows) / count, 2)
        min_wait = round(min(r["min_wait_time_sec"] for r in rows), 2)
        max_wait = round(max(r["max_wait_time_sec"] for r in rows), 2)

        aggregate_summary.append({
            "direction": direction,
            "algorithm": algorithm,
            "files_count": count,
            "avg_duration_to_pass_n_sec": avg_duration,
            "avg_wait_time_sec": avg_wait,
            "min_wait_time_sec": min_wait,
            "max_wait_time_sec": max_wait,
        })

    aggregate_file = os.path.join(SUMMARY_DIR, f"first_{N}_vehicles_aggregate_summary.csv")
    with open(aggregate_file, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=aggregate_summary[0].keys())
        writer.writeheader()
        writer.writerows(aggregate_summary)
    print(f"✅ Aggregate summary saved to: {aggregate_file}")

    print(f"Processed {total_files} files, found data in {files_with_data} files.")

if __name__ == "__main__":
    analyze_first_n_by_direction_algorithm()
