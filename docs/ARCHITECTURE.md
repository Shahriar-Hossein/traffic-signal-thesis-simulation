# Simulation Architecture — Current State

**As of:** 25 August 2026, branch `feature/modify-data-collection`.
**Scope:** what each file does, how the pieces are wired, what runs on which thread, and where data lands on disk.
**Includes** the vehicle-count run mode, implemented 25 August 2026 ([RUN_MODE_VEHICLE_COUNT_PLAN.md](RUN_MODE_VEHICLE_COUNT_PLAN.md)).

---

## 1. One-paragraph summary

A pygame program draws a four-way intersection. One background thread generates vehicles at a rate that switches between three traffic conditions; another background thread runs the signal controller, which decides which direction gets green and for how long. The pygame main thread renders every frame and — as a side effect of rendering — advances every vehicle's physics. Each vehicle writes one CSV row the moment it crosses its stop line; each signal change writes one CSV row too. The run ends either when a wall-clock timer expires (`run_mode = 'time'`) or when a fixed quota of vehicles has all crossed (`run_mode = 'vehicles'`) — the two modes write to entirely separate log trees. Offline analyzer scripts walk the CSV trees afterwards and produce summaries.

---

## 2. Entry points

| Command | What it does |
|---|---|
| `python3 main.py` | One simulation run, one pygame window. All settings come from [state.py](../state.py) and [config.py](../config.py) — there are no CLI arguments. |
| `python3 run_simulation.py` | Spawns 5 `main.py` subprocesses 1.5 s apart and waits for all to finish ([run_simulation.py:19](../run_simulation.py#L19)). This is how a batch of repeat runs is produced. |
| `python3 analyzers/analyze_log.py` | Offline. Reads `data/logs/**` (**time runs only**), writes `data/summary_logs/simulation_summary.csv`. |
| `python3 analyzers/analyze_count_log.py` | Offline. Reads `data/logs_by_count/**` (**vehicle-count runs only**), writes `data/summary_count_logs/count_simulation_summary.csv`. |
| `python3 analyzers/analyze_signal_log.py` | Offline. Reads `data/log_signals/**`, writes `data/summary_signals/`. |
| `python3 analyzers/analyze_first_n_vehicles.py` | Offline. Pools the first N vehicles per mode across files. |

Changing what a run does means editing `state.py` (mode, duration, load skew) and re-running. There is no config-per-run mechanism.

---

## 3. Directory map

| Path | Role |
|---|---|
| [main.py](../main.py) | pygame bootstrap, thread launch, render loop, **termination condition** |
| [state.py](../state.py) | Global mutable run state + the run's settings (mode, duration, skew) |
| [config.py](../config.py) | Static constants: geometry, speeds, timings, turn tables, load rates |
| [run_simulation.py](../run_simulation.py) | Batch runner (subprocesses) |
| [core/initializer.py](../core/initializer.py) | Builds the 4 signals, then dispatches to one controller (blocks forever) |
| [core/generator.py](../core/generator.py) | Vehicle arrival process |
| [core/cycle_fixed.py](../core/cycle_fixed.py) | Baseline controller: fixed order, fixed green |
| [core/cycle_priority.py](../core/cycle_priority.py) | Proposed controller: queue-weighted order + adaptive green |
| [core/cycle_fairness_priority.py](../core/cycle_fairness_priority.py) | Variant with early-exit on empty lanes |
| `core/cycle_priority copy.py` | **Dead file.** Not imported anywhere. |
| [core/updater.py](../core/updater.py) | Decrements the on-screen countdown numbers |
| [models/vehicle.py](../models/vehicle.py) | Vehicle sprite: physics, car-following, turning, wait accounting, crossing log |
| [models/traffic_signal.py](../models/traffic_signal.py) | Plain data holder + the global `signals` list |
| [utils/logger.py](../utils/logger.py) | CSV file naming and writing (both log types) |
| [utils/counters.py](../utils/counters.py) | Queue-length queries used by controllers and the HUD |
| [utils/draw.py](../utils/draw.py) | All blitting — **and it calls `vehicle.move()`** |
| [analyzers/analyze_count_log.py](../analyzers/analyze_count_log.py) | Offline summary for vehicle-count runs |
| `analyzers/` | Offline post-processing |
| `data/` | Output CSVs |
| `images/` | Sprites, background, signal heads |
| `previous_versions/` | **Dead.** Old monolithic versions kept for reference. |

---

## 4. Threads

Three threads, started in [main.py:30-43](../main.py#L30-L43).

```
main thread (pygame)                 InitializationThread            VehicleGeneratorThread
─────────────────────                ────────────────────            ──────────────────────
init_logger()                        initialize()                    generateVehicles()
start threads  ─────────────────────► build 4 TrafficSignal   ─┐     ─┐
                                      dispatch to controller   │      │
while True:                           (never returns)          │      │ pick condition
  check elapsed >= duration           ┌────────────────────────┘      │ every 120 s
  handle pygame events                │ while state.running:          │
  blit background                     │   pick green direction        │ pick direction
  draw_traffic_signals()              │   log_signal_change()         │ by weights
  draw_all_vehicles() ──► move()      │   sleep(1) × green_time       │
  draw counts                         │   yellow phase                │ Vehicle(...)
  display.update()                    │   sleep(1) × yellow           │ sleep(1/rate)
  clock.tick(60)                      └──────────────────────────────┘
```

Both background threads are `daemon=True`, so `sys.exit()` on the main thread kills them mid-sleep with no cleanup.

**All vehicle physics runs on the main thread.** [draw_all_vehicles](../utils/draw.py#L40-L46) blits *and* calls `vehicle.move()` in the same loop, so simulation speed is tied to the 60 FPS cap and to render cost. This is the single most important coupling in the codebase.

Shared-state contention is low by accident rather than by design: the generator thread only appends to `state.vehicles[dir][lane]`, the controller thread only writes `state.currentGreen` / `state.currentYellow` and signal timers, and the main thread does everything else. There are no locks anywhere.

---

## 5. Startup sequence

1. `main()` initialises pygame and the clock ([main.py:47-49](../main.py#L47-L49)).
2. `start_simulation_threads()` calls `init_logger(state.duration, state.uneven_mode)` **first** — the log file and its header exist before any vehicle can be created ([main.py:34](../main.py#L34)).
3. `InitializationThread` runs `initialize()`: clears and rebuilds the 4 `TrafficSignal` objects, then calls one of the three cycle functions based on `state.currentMode` ([core/initializer.py:24-30](../core/initializer.py#L24-L30)). That call never returns.
4. `VehicleGeneratorThread` runs `generateVehicles(uneven_mode=...)`.
5. Every controller opens with a hard-coded **10-second all-red phase** so a queue accumulates before the first green (e.g. [core/cycle_fixed.py:20-34](../core/cycle_fixed.py#L20-L34)). During this window `state.currentGreen = -1`.
6. The main thread enters the frame loop.

---

## 6. The frame loop and how a run ends

[main.py:67-96](../main.py#L67-L96) asks `should_stop(elapsed)` once per frame. There are two ways a run ends, chosen by `state.run_mode`:

```python
def should_stop(elapsed):
    if state.run_mode == 'vehicles':
        target = state.target_vehicle_count
        if state.vehicles_generated >= target and state.vehicles_crossed >= target:
            return 'target_reached'
        if elapsed >= state.count_mode_timeout:
            return 'timeout'
        return None
    return 'duration' if elapsed >= state.duration else None
```

| `run_mode` | Ends when | `stop_reason` |
|---|---|---|
| `'time'` | `elapsed >= state.duration` | `duration` |
| `'vehicles'` | all `target_vehicle_count` vehicles generated **and** all of them crossed | `target_reached` |
| `'vehicles'` | `elapsed >= state.count_mode_timeout` — safety cap, run is truncated | `timeout` |
| either | window closed by hand | `user_quit` |

`shutdown(reason, elapsed, started_at)` then sets `state.stop_reason`, sets `state.running = False`, writes the metadata sidecar (count mode only), prints a one-line summary, and exits. Closing the window now goes through the same path instead of a bare `sys.exit()`, so a manually stopped run also leaves a record behind.

In count mode the target-reached branch waits `COUNT_MODE_DRAIN_SEC` (1.5 s) of extra rendering before quitting, so vehicles mid-turn finish on screen. That is cosmetic only — every vehicle is already logged by then.

**Termination in count mode is a crossing count, not a queue-empty check.** `log_vehicle` fires exactly once per vehicle at the stop line, and `state.vehicles_crossed` is incremented on the same line ([models/vehicle.py:391-400](../models/vehicle.py#L391-L400)), so "the last vehicle crossed the traffic signal" is one integer comparison with no ambiguity about vehicles mid-turn or off-screen.

**Why the two modes produce differently-shaped data:**

- A **time** run stops the clock mid-stream. Every vehicle still queued at that instant has never crossed and therefore has **no row in the CSV** — and those are exactly the longest-waiting vehicles, so mean wait is biased low, by a different amount per controller.
- A **count** run logs every vehicle it generates, so the sample is complete. In exchange, wall-clock duration becomes an *output* rather than an input (recorded in the sidecar), and the tail of the run drains under zero arrivals — a condition no time run experiences.

Neither is wrong, but they are not the same population. This is why the two log trees are kept apart (§11).

`start_time` is taken at [main.py:129](../main.py#L129), *after* the threads start, so the 10 s all-red phase is inside the measured duration in both modes.

## 7. Shared state ([state.py](../state.py))

| Name | Written by | Read by | Meaning |
|---|---|---|---|
| `vehicles` | Vehicle `__init__` / `_remove_from_simulation` | controllers, counters, vehicle car-following | `dict[direction][lane] -> list[Vehicle]`, plus an unused `'crossed'` key |
| `vehicle_simulation` | Vehicle `__init__` / removal | `draw_all_vehicles`, post-turn gap search | pygame sprite group — the render/physics set |
| `waiting_time` | *nobody* | *nobody* | **Dead field.** Per-vehicle wait lives on the vehicle. |
| `currentGreen` | controller thread | vehicle `move()`, draw | index 0-3, or `-1` during all-red |
| `currentYellow` | controller thread | vehicle `move()`, draw | 0/1 |
| `currentMode` | edited by hand | `initialize()`, `init_logger`, `log_vehicle` | `'priority'` \| `'fixed'` \| `'fairness_priority'` — picks controller **and** names the log file |
| `running` | main thread (at exit) | controller + generator loops | shutdown flag |
| `traffic_condition` | generator | nothing yet | current `'high'`/`'medium'`/`'low'` — exposed but unlogged |
| `uneven_mode` | edited by hand | generator (direction weights), `init_logger` (folder) | demand skew |
| `duration` | edited by hand | main loop, `init_logger` (folder + filename) | run length in seconds — **time mode only** |
| `run_mode` | edited by hand | `should_stop`, `init_logger`, generator | `'time'` \| `'vehicles'` — picks the stop condition **and** the log tree |
| `target_vehicle_count` | edited by hand | generator quota, `should_stop`, `init_logger` (folder) | vehicles to generate — **count mode only** |
| `count_mode_timeout` | edited by hand | `should_stop` | safety cap so a wedged run cannot hang a batch |
| `vehicles_generated` | generator thread **only** | `should_stop`, generator guard | quota progress |
| `vehicles_crossed` | main thread **only** | `should_stop` | crossings so far |
| `stop_reason` | main thread at exit | meta sidecar | why the run ended |

Settings are selected by commenting/uncommenting lines. Anything that names a log path is read from here.

The three counters have **one writer each** — `vehicles_generated` is touched only by the generator thread, `vehicles_crossed` only by the main thread — which is why no lock is needed. Preserve that if either counter is ever read or written from a controller.

---

## 8. Vehicle lifecycle

**Birth** — [core/generator.py](../core/generator.py) loops while `state.running`, and in count mode also stops once the quota is filled:
- every `trafficConditionInterval` (120 s) it picks a new condition, never repeating the current one ([core/generator.py:12-18](../core/generator.py#L12-L18));
- picks a random type (car/bus/truck/bike), a direction from the `uneven_mode` weight table, and a lane in 0-2;
- constructs a `Vehicle`, which self-registers into `state.vehicles` and `state.vehicle_simulation`;
- increments `state.vehicles_generated` and sleeps `1 / trafficConditions[condition]` seconds. Arrivals are **deterministic within a phase**, not Poisson.

In `run_mode = 'vehicles'` the loop breaks once `vehicles_generated >= target_vehicle_count`; the generator thread ends there while the simulation keeps running until the last of those vehicles crosses. The traffic-condition switching is deliberately unchanged, so count runs face the same variable load as time runs — which also means run length varies with the (unseeded) condition sequence drawn.

**Placement** — `Vehicle.__init__` ([models/vehicle.py:71-104](../models/vehicle.py#L71-L104)) computes its stop position from the vehicle ahead in the same lane, and spawns off-screen behind it if the lane is occupied. Turn intent is decided at birth: lanes 0 and 2 turn with probability `turnProbability = 0.5`, and the trigger offset is solved analytically so the arc lands on the target lane ([models/vehicle.py:140-190](../models/vehicle.py#L140-L190)).

**Motion** — `move()` ([models/vehicle.py:326-448](../models/vehicle.py#L326-L448)), once per frame per vehicle, in this order:
1. post-turn straight-line motion with a gap check, or
2. active turn arc (rotating sprite over `turnFrames` frames), or
3. normal lane motion: `green_go` for its direction, obstacle check against the nearest non-turn-completed predecessor, then advance.

**Crossing (the logged event)** — [models/vehicle.py:391-399](../models/vehicle.py#L391-L399):

```python
if not self.crossed:
    if <past stopLines[direction]>:
        self.crossed = 1
        state.vehicles_crossed += 1
        log_vehicle(self)
```

This is the one and only place a vehicle row is written, and it fires exactly once per vehicle. "Crossing the traffic signal" = passing the stop line, *not* leaving the screen. The counter increment sits here so count-mode termination and the CSV can never disagree.

**Wait accounting** — [models/vehicle.py:431-444](../models/vehicle.py#L431-L444). A vehicle that did not move this frame starts a wait timer; when it moves again the elapsed time is added to `actual_wait_time`. The value written to the CSV is therefore the wait accumulated **up to the crossing moment**; waiting done after the stop line (e.g. blocked mid-turn) is never logged.

**Death** — once `crossed` and 100 px outside the screen, `_remove_from_simulation()` drops it from the sprite group and the lane list and re-indexes the survivors ([models/vehicle.py:468-489](../models/vehicle.py#L468-L489)).

---

## 9. Signal control

All three controllers share the same skeleton: 10 s all-red → loop while `state.running` → for each direction in some order: set green, `log_signal_change`, sleep 1 s per green second, force a yellow phase (which resets every vehicle's `stop` back to `defaultStop`), sleep the yellow, restore default timers.

| | order | green time | early exit |
|---|---|---|---|
| `fixed` | fixed `[0,1,2,3]` | `defaultGreen` = 24 s | no |
| `priority` | sorted by weighted queue, **re-sorted after every phase** ([core/cycle_priority.py:86-95](../core/cycle_priority.py#L86-L95)) | `clamp(6, count × 0.75, 24)` | no |
| `fairness_priority` | sorted once per full cycle | `clamp(6, count × 0.67, 18)` | yes, if all lanes ≤ 1 vehicle and t ≥ 6 |

The queue metric is `get_weighted_vehicle_counts()` ([utils/counters.py:13-29](../utils/counters.py#L13-L29)) which weights each uncrossed vehicle by `1 / speed` — bikes count least, trucks most. The on-screen HUD uses the unweighted `get_vehicle_counts()` instead, so the number you see is not the number the controller optimises.

Timing is `time.sleep(1)` in a Python thread, so green phases drift slightly longer than nominal.

---

## 10. Logging

Two CSVs per run (plus a JSON sidecar in count mode), all named by [utils/logger.py](../utils/logger.py) at `init_logger` time. The module keeps two globals — `log_filename` and `signal_log_filename` — plus the shared `run_basename`.

### 10.1 Destination depends on the run mode

`init_logger` branches once, up front. The two modes never share a folder, because every analyzer rebuilds a run's identity from its folder path (§11).

| | time mode | count mode |
|---|---|---|
| Vehicle log | `data/logs/{uneven_mode}/{duration}/` | `data/logs_by_count/{uneven_mode}/{N}/` |
| Signal log | `data/log_signals/{uneven_mode}/{duration}/` | `data/log_signals_by_count/{uneven_mode}/{N}/` |
| Basename | `{mode}_log_{duration}_{ts}` | `{mode}_countlog_{N}_{ts}` |
| Sidecar | none | `{basename}_meta.json` |

The `countlog` token means a file stays identifiable as a count run even after it is copied out of its folder, while `filename.split("_")[0]` still yields the controller name, so analyzer parsing carries over unchanged.

### 10.2 Vehicle log

Written by `log_vehicle()`, one row per crossing, opened and closed per row. **The schema is identical in both modes** — same six columns, same order — so the count analyzer is a near-copy of the existing one.

| Column | Source |
|---|---|
| `timestamp` | wall clock at crossing, 1 s resolution |
| `vehicle_id` | `id(vehicle)` — **memory address, reused after GC**; not a stable identity |
| `vehicle_type` | car/bus/truck/bike |
| `direction` | origin direction (not the post-turn direction) |
| `mode` | `state.currentMode` |
| `wait_time_sec` | `actual_wait_time` at crossing |

### 10.3 Signal log

Columns `timestamp, direction`, one row per green change. The path is now set explicitly in `init_logger` alongside the vehicle log. It used to be derived from the vehicle-log path by `log_filename.replace("logs", "log_signals")`, which rewrote *every* occurrence of `logs` in the absolute path — that derivation is gone.

### 10.4 Run metadata sidecar (count mode)

`write_run_meta()` is called once from `shutdown()` and writes `{basename}_meta.json` next to the vehicle log:

```json
{"run_mode": "vehicles", "controller": "priority", "uneven_mode": "even",
 "vehicle_log": "...csv", "signal_log": "..._signal.csv",
 "target_vehicle_count": 50, "vehicles_generated": 50, "vehicles_crossed": 50,
 "duration_sec": 48.57, "stop_reason": "target_reached",
 "started_at": "...", "ended_at": "..."}
```

JSON was chosen deliberately: all analyzers filter on `.csv`, so a sidecar can never contaminate a summary. `duration_sec` is the headline number for a count run — with the vehicle count fixed, a shorter run is a better controller. `stop_reason` is what separates a complete run from a truncated one.

### 10.5 What is still not logged

The active `traffic_condition`, the green time granted per phase, per-vehicle turn intent. Time-mode runs still have no sidecar.

## 11. Data on disk

```
data/
├── logs/{uneven_mode}/{duration}/{mode}_log_{duration}_{ts}.csv        ← TIME runs: crossings
├── log_signals/{uneven_mode}/{duration}/..._signal.csv                 ← TIME runs: signal changes
├── logs_by_count/{uneven_mode}/{N}/{mode}_countlog_{N}_{ts}.csv        ← COUNT runs: crossings
│                                  {mode}_countlog_{N}_{ts}_meta.json   ← COUNT runs: run metadata
├── log_signals_by_count/{uneven_mode}/{N}/..._signal.csv               ← COUNT runs: signal changes
├── summary_logs/simulation_summary.csv                                 ← analyze_log.py
├── summary_count_logs/count_simulation_summary.csv                     ← analyze_count_log.py
├── summary_signals/                                                    ← analyze_signal_log.py
└── summary_first_n/                                                    ← analyze_first_n_*.py
```

The two run types are **siblings, not nested**. `analyze_log.py` walks `data/logs` and never descends into `data/logs_by_count`, so the existing summaries are untouched by count runs, and vice versa.

The **folder path is the metadata**. Every analyzer reconstructs the run's identity by parsing it:

```python
parts = root.split(os.sep)
uneven_mode = parts[-2]        # 'even'
duration_folder = parts[-1]    # '600'
mode_part = filename.split("_")[0]   # 'priority'
label = f"{mode_part}_{uneven_mode}_{duration_folder}"
```

([analyzers/analyze_log.py:37-54](../analyzers/analyze_log.py#L37-L54), same shape in the other two.) `analyze_log.py` walks **all** of `data/logs` and groups everything it finds under those labels.

**This is the constraint that dictated the layout:** a count run stored at `data/logs/even/500/` would be labelled `priority_even_500` and silently pooled with duration-600 runs, because the analyzer cannot tell a vehicle target from a duration. A sibling root is the only clean separation — hence `logs_by_count`. `analyze_count_log.py` applies the same parsing to its own root and labels runs `{mode}_{uneven_mode}_n{N}` so the two label spaces cannot collide either.

File filters used by the analyzers, worth knowing:
- `analyze_log.py` — any `*.csv` under `data/logs` (it does **not** exclude `_signal.csv`; those live in a different root so it happens to be safe).
- `analyze_signal_log.py` — `*.csv` with `signal` in the name.
- `analyze_first_n_vehicles.py` — `*.csv` without `signal` in the name, mode from `filename.split("_")[0]`, only `fixed`/`priority`.
- `analyze_count_log.py` — `*.csv` without `signal` in the name, under `data/logs_by_count`; reads each run's `_meta.json`, **excludes `stop_reason == 'timeout'` runs from the pooled statistics**, and warns when a file's row count does not equal its vehicle target.
- Non-`.csv` files (including the `_meta.json` sidecars) are ignored by all four.

---

## 12. Configuration map

| I want to change | Edit |
|---|---|
| Controller (fixed / priority / fairness) | `state.currentMode` |
| **How the run ends (time vs vehicle count)** | `state.run_mode` — `'time'` or `'vehicles'` |
| Run length *(time mode)* | `state.duration` |
| **Vehicle target** *(count mode)* | `state.target_vehicle_count` |
| **Safety cap** *(count mode)* | `state.count_mode_timeout` |
| Demand skew | `state.uneven_mode` |
| Arrival rates | `trafficConditions` [config.py:162-166](../config.py#L162-L166) |
| How often load switches | `trafficConditionInterval` [config.py:169](../config.py#L169) |
| Fixed-mode green time | `defaultGreen` [config.py:2](../config.py#L2) |
| Adaptive green formula | inside each cycle file |
| Turn rate | `turnProbability` [config.py:115](../config.py#L115) |
| Runs per batch | `run_simulations(5)` [run_simulation.py:19](../run_simulation.py#L19) |

---

## 13. Fragile points

Ranked by how likely they are to bite a change:

1. **Physics is inside the renderer.** `vehicle.move()` is called from `draw_all_vehicles`. A frame drop is a physics slowdown.
2. **`log_filename` / `signal_log_filename` are module globals**, set once in `init_logger`. One run per process is baked in. *(The old `str.replace`-derived signal path is gone.)*
3. **The folder path is the only run metadata**, and every analyzer parses it positionally.
4. **`id(vehicle)` as `vehicle_id`** is not unique over a run — CPython reuses addresses after a vehicle is despawned and collected. `unique_vehicles` in the summary undercounts.
5. **No locks on shared state** — safe today only because each thread touches a disjoint slice.
6. **Termination is still `sys.exit()` from the render loop.** `shutdown()` sets `state.running = False` immediately before it, so the daemon threads never actually observe the flag — there is no join and no flush barrier. Rows are safe only because `log_vehicle` opens and closes the file per row.
7. **The folder bucket is `duration` in one mode and `target_vehicle_count` in the other.** Two different quantities occupy the same position in the path; only the root directory distinguishes them.
8. **The traffic-condition sequence is unseeded**, so two runs with the same settings face different load. In count mode this directly moves the headline number (`duration_sec`), so paired comparisons need many runs — or a seed.
9. **Dead code** — `core/cycle_priority copy.py`, `previous_versions/`, `state.waiting_time`, the `'crossed'` key in `state.vehicles`.
