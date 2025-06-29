import subprocess
import time

def run_simulations(num_instances):
    processes = []
    for i in range(num_instances):
        cmd = ["python3", "main.py"]
        print(f"Starting simulation instance {i+1}...")
        proc = subprocess.Popen(cmd)
        processes.append(proc)
        time.sleep(1)  # small delay between starts

    # Wait for all to finish (optional)
    for i, proc in enumerate(processes):
        proc.wait()
        print(f"Simulation instance {i+1} finished.")

if __name__ == "__main__":
    run_simulations(12)
