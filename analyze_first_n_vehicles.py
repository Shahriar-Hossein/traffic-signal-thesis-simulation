import os
import csv
from datetime import datetime

LOG_ROOT = "logs"
SUMMARY_DIR = "summary_first_n"
os.makedirs(SUMMARY_DIR, exist_ok=True)

VEHICLES_PER_FILE = 50  # Max vehicles per file to take
N_TOTAL = 800  # Total vehicles to include in the summary per mode
MODES = ['fixed', 'priority']  # Modes to compare


def read_log_file(filepath):
    with open(filepath, mode='r') as f:
        return list(csv.DictReader(f))


def analyze_first_n_total_vehicles():
    records_by_mode = {mode: [] for mode in MODES}
    sim_duration_by_mode = {mode: 0.0 for mode in MODES}  # Sum of per-file simulation durations
    vehicles_count_by_mode = {mode: 0 for mode in MODES}

    for root, _, files in os.walk(LOG_ROOT):
        for filename in files:
            if not filename.endswith(".csv") or "signal" in filename:
                continue

            mode = filename.split("_")[0]
            if mode not in MODES:
                continue

            # If already collected enough vehicles, skip reading more files for this mode
            if vehicles_count_by_mode[mode] >= N_TOTAL:
                continue

            filepath = os.path.join(root, filename)
            records = read_log_file(filepath)

            file_records = []
            collected = 0
            max_to_collect = min(VEHICLES_PER_FILE, N_TOTAL - vehicles_count_by_mode[mode])

            for r in records:
                if collected >= max_to_collect:
                    break
                try:
                    r['timestamp_obj'] = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
                    r['wait_time'] = float(r['wait_time_sec'])
                    file_records.append(r)
                    collected += 1
                except Exception as e:
                    print(f"⚠️ Skipping row in {filename}: {e}")

            if not file_records:
                continue

            # Calculate simulation duration for this file portion (max timestamp - min timestamp)
            file_start = min(r['timestamp_obj'] for r in file_records)
            file_end = max(r['timestamp_obj'] for r in file_records)
            file_duration = (file_end - file_start).total_seconds()
            sim_duration_by_mode[mode] += file_duration

            # Add file records to mode's records
            records_by_mode[mode].extend(file_records)
            vehicles_count_by_mode[mode] += len(file_records)

            # Stop reading files if we have reached the total desired vehicles for this mode
            if vehicles_count_by_mode[mode] >= N_TOTAL:
                print(f"Reached {N_TOTAL} vehicles for mode {mode}, stopping file read.")

    combined_results = []

    for mode in MODES:
        all_records = records_by_mode[mode]
        if not all_records:
            print(f"⚠️ No records found for mode: {mode}")
            continue

        # Sort by timestamp just in case
        sorted_records = sorted(all_records, key=lambda r: r['timestamp_obj'])
        # Truncate to N_TOTAL (should be redundant since we limited earlier)
        truncated = sorted_records[:N_TOTAL]

        if not truncated:
            print(f"⚠️ No records to analyze for mode: {mode}")
            continue

        wait_times = [r['wait_time'] for r in truncated]

        result = {
            "mode": mode,
            "total_vehicles": len(truncated),
            "sim_duration_sec": round(sim_duration_by_mode[mode], 2),  # Sum of per-file durations actually used
            "avg_wait_time_sec": round(sum(wait_times) / len(wait_times), 2),
            "min_wait_time_sec": round(min(wait_times), 2),
            "max_wait_time_sec": round(max(wait_times), 2)
        }
        combined_results.append(result)

    if not combined_results:
        print("⚠️ No data found to write.")
        return

    output_path = os.path.join(SUMMARY_DIR, f"first_{N_TOTAL}_vehicles_comparison.csv")
    with open(output_path, mode='w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=combined_results[0].keys())
        writer.writeheader()
        writer.writerows(combined_results)

    print(f"✅ Saved combined summary for first {N_TOTAL} vehicles to: {output_path}")


if __name__ == "__main__":
    analyze_first_n_total_vehicles()
