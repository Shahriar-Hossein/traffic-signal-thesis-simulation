# Traffic Signal Simulation

A Pygame-based traffic intersection simulator with multiple control algorithms and CSV logging/analysis utilities.

## Features

- Visual traffic intersection simulation with moving vehicles
- Multiple control strategies:
	- `fixed`
	- `priority`
	- `fairness_priority`
- Configurable traffic distribution (`even`, directional bias, and paired-direction bias)
- Per-run CSV logs for:
	- vehicle waiting times
	- signal change events
- Offline analyzers to compare algorithm performance

## Requirements

- Linux (or any OS that supports Python + Pygame)
- Python 3.9+
- `pip`

Only external Python dependency used by the current code:

- `pygame`

## Setup

From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pygame
```

## Run The Simulation

```bash
python3 main.py
```

The simulation window opens and runs until the configured duration is reached.

## Main Runtime Configuration

Edit `state.py` before running:

- `currentMode`:
	- `"fixed"`
	- `"priority"`
	- `"fairness_priority"`
- `uneven_mode`:
	- `"even"`
	- single-direction heavy: `"up"`, `"down"`, `"left"`, `"right"`
	- paired directions: `"up_down"`, `"left_right"`
- `duration` (seconds), for example:
	- `300` for 5 minutes
	- `600` for 10 minutes

## Vehicle Generation Rate

Vehicle generation logic is in `core/generator.py`.

- A short sleep is applied every 5 generated vehicles (`time.sleep(1)`), which makes generation bursty.
- If you want to tune arrival rate, adjust the sleep logic in `generateVehicles()`.

## Run Multiple Simulations Automatically

Use the helper script:

```bash
python3 run_simulation.py
```

Current behavior in `run_simulation.py`:

- starts 10 instances
- waits `1.5` seconds between launches

Adjust `run_simulations(10)` and `time.sleep(1.5)` in that file as needed.

## Output Logs

Generated logs are stored under:

- Vehicle logs: `data/logs/<uneven_mode>/<duration>/...csv`
- Signal logs: `data/log_signals/<uneven_mode>/<duration>/..._signal.csv`

File names include algorithm mode and timestamp, for example:

- `priority_log_300_YYYYMMDD_HHMMSS.csv`
- `fixed_log_300_YYYYMMDD_HHMMSS_signal.csv`

## Analyze Results

Run analyzers from project root:

```bash
python3 analyzers/analyze_log.py
python3 analyzers/analyze_signal_log.py
python3 analyzers/analyze_first_n_vehicles.py
python3 analyzers/analyze_first_n_vehicles_by_direction.py
```

Summary outputs are written to:

- `data/summary_logs/simulation_summary.csv`
- `data/summary_signals/signal_summary.csv`
- `data/summary_first_n/first_800_vehicles_comparison.csv` (default)
- `data/summary_first_vehicles_by_direction_algorithm/` (multiple CSV outputs)

## Notes

- If Pygame fails to open a window on Linux, ensure desktop/graphics support is available in your environment.
- The simulator is designed for interactive/graphical execution, not headless mode.