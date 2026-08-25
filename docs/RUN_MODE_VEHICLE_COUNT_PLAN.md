# Modification Plan — Vehicle-Count Run Mode

**Goal:** the simulation can end in one of two ways, and each way writes its own log set that the other never touches.

| Run mode | Ends when | Log root |
|---|---|---|
| `time` *(exists today)* | wall clock reaches `state.duration` | `data/logs/`, `data/log_signals/` — **unchanged** |
| `vehicles` *(new)* | all `N` generated vehicles have crossed the stop line | `data/logs_by_count/`, `data/log_signals_by_count/` |

**Status: implemented and verified, 25 August 2026.** Phases 1-5 and 7-9 are done; Phase 6's optional CLI was deliberately not built (see the status note at the end). Verification results are in §Phase 8.

**Hard requirement:** nothing in this plan may change the file paths, filenames, CSV schema, or row content produced by a time-based run, and no count-mode file may land anywhere `analyze_log.py` / `analyze_signal_log.py` / `analyze_first_n_vehicles.py` will find it. Background for every reference below is in [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 0. Why count mode is worth having

Not just convenience — it fixes a measurement bias.

A time-based run stops the clock mid-stream. Every vehicle still queued at that instant has never crossed its stop line, so it has **no row in the CSV** ([ARCHITECTURE.md §6](ARCHITECTURE.md)). The vehicles excluded are exactly the ones that waited longest, so mean wait is biased low, and biased low by a different amount for each controller (a controller with a longer tail loses more of it). Count mode logs every vehicle it generates, so the sample is complete and the two arms are compared on the same population.

Two properties of count mode to be aware of when reading its results:

1. **Run length becomes a random variable.** The same N vehicles take longer to clear under a `high`-heavy condition sequence than a `low`-heavy one. Wall-clock duration becomes an *output*, not an input — record it (Step 2.4) and report it.
2. **The tail drains under zero arrivals.** Once the generator stops, the last vehicles face emptying queues and short waits, which no time-mode run ever experiences. This is a systematic difference in the shape of the data, and it is the reason the two log sets must never be pooled — even setting aside the folder-parsing problem.

Neither is a blocker. Both are things to state when the numbers are written up.

---

## 1. Design decisions

**Termination signal is a crossing count, not a queue-empty check.** `log_vehicle` fires exactly once per vehicle at the stop line ([models/vehicle.py:391-399](../models/vehicle.py#L391-L399)). Counting there means "the last vehicle crossed the traffic signal" is a single integer comparison, with no ambiguity about vehicles mid-turn or off-screen. Vehicles still finishing their turn when the count completes are allowed a short drain (Step 5.3) purely so the visuals end cleanly; they are already logged.

**Separate log root, not a new folder inside `data/logs/`.** Every analyzer reconstructs a run's identity from `parts[-2]`/`parts[-1]` of the folder path ([ARCHITECTURE.md §11](ARCHITECTURE.md)). A run stored at `data/logs/even/500/` would be labelled `priority_even_500` and silently pooled with duration-600 runs. A sibling root is the only clean separation.

**Identical CSV schema in both modes.** Same six columns, same order. Run-level facts (target N, actual duration, termination reason) go into a per-run JSON sidecar instead of new columns. This keeps the count analyzer a near-copy of the existing one, and JSON files are ignored by all three current analyzers, so a sidecar can never contaminate anything.

**Distinct filename token.** `{mode}_countlog_{N}_{ts}.csv` rather than `{mode}_log_{N}_{ts}.csv`, so a file is identifiable as a count run even after it is copied out of its folder. `filename.split("_")[0]` still yields the mode, so analyzer parsing carries over unchanged.

**A safety timeout is mandatory.** If one vehicle wedges, a count run never ends, and `run_simulation.py` blocks on `proc.wait()` forever. `count_mode_timeout` caps the run and records `stop_reason = "timeout"` so a truncated run is never mistaken for a complete one.

**Settings stay in `state.py`,** edited by hand like everything else today. CLI flags are an optional add-on (Phase 6) that defaults to the `state.py` values, so the existing workflow keeps working untouched.

---

## Phase 1 — Run-mode state

- [x] **1.1** Add to [state.py](../state.py):
  ```python
  # how the run ends: 'time' (wall clock) or 'vehicles' (fixed vehicle count)
  run_mode = 'time'

  # --- vehicles mode ---
  target_vehicle_count = 500   # generate N, end when all N have crossed
  count_mode_timeout   = 1800  # safety cap in seconds; run aborts if exceeded

  # --- live counters (written at runtime, not settings) ---
  vehicles_generated = 0   # incremented by the generator thread
  vehicles_crossed   = 0   # incremented by the main thread at each crossing
  stop_reason        = None  # 'duration' | 'target_reached' | 'timeout' | 'user_quit'
  ```
- [x] **1.2** Leave `duration` exactly as it is — count mode ignores it, time mode still uses it.
- [x] **1.3** Comment the two counters as being owned by one thread each: `vehicles_generated` only by the generator, `vehicles_crossed` only by the main thread. No lock needed as long as that holds ([ARCHITECTURE.md §4](ARCHITECTURE.md)).

---

## Phase 2 — Logger: two destinations

All in [utils/logger.py](../utils/logger.py). This is the only phase that touches code shared by both modes, so it needs the most care.

- [x] **2.1** Replace the single `log_filename` global with two: `log_filename` and `signal_log_filename`, both set inside `init_logger`.
- [x] **2.2** Rewrite `log_signal_change` to use `signal_log_filename` directly and delete the `.replace("logs", "log_signals")` derivation ([utils/logger.py:71-73](../utils/logger.py#L71-L73)). This also fixes the latent bug where any absolute path containing `logs` gets mangled.
- [x] **2.3** Branch the path construction on run mode:
  ```python
  def init_logger(duration_sec, uneven_mode=None):
      global log_filename, signal_log_filename
      mode_label = state.currentMode
      ts = datetime.now().strftime('%Y%m%d_%H%M%S')

      if state.run_mode == 'vehicles':
          bucket    = str(state.target_vehicle_count)
          log_root  = "logs_by_count"
          sig_root  = "log_signals_by_count"
          basename  = f"{mode_label}_countlog_{bucket}_{ts}"
      else:
          bucket    = str(duration_sec)
          log_root  = "logs"
          sig_root  = "log_signals"
          basename  = f"{mode_label}_log_{bucket}_{ts}"

      log_dir = os.path.join(BASE_DATA_DIR, log_root, uneven_mode, bucket)
      sig_dir = os.path.join(BASE_DATA_DIR, sig_root, uneven_mode, bucket)
      os.makedirs(log_dir, exist_ok=True)
      os.makedirs(sig_dir, exist_ok=True)

      log_filename        = os.path.join(log_dir, f"{basename}.csv")
      signal_log_filename = os.path.join(sig_dir, f"{basename}_signal.csv")
      # ... existing header write, unchanged ...
  ```
  The `else` branch must produce byte-identical paths to today's code — verify in Step 8.1.
- [x] **2.4** Add `write_run_meta(**fields)`, called once at shutdown, writing `{basename}_meta.json` next to the CSV. Count mode only, for now:
  ```json
  {"run_mode": "vehicles", "controller": "priority", "uneven_mode": "even",
   "target_vehicle_count": 500, "vehicles_generated": 500, "vehicles_crossed": 500,
   "duration_sec": 412.7, "stop_reason": "target_reached",
   "started_at": "...", "ended_at": "..."}
  ```
- [x] **2.5** Leave `log_vehicle`'s row format completely alone.

---

## Phase 3 — Generator stops at N

In [core/generator.py](../core/generator.py).

- [x] **3.1** Change the loop guard so it also stops once the quota is filled:
  ```python
  while state.running:
      if state.run_mode == 'vehicles' and state.vehicles_generated >= state.target_vehicle_count:
          print(f"Generated all {state.target_vehicle_count} vehicles. Generator stopping.")
          break
  ```
- [x] **3.2** Increment `state.vehicles_generated` immediately after each successful `Vehicle(...)` construction ([core/generator.py:104-109](../core/generator.py#L104-L109)).
- [x] **3.3** Leave the traffic-condition switching untouched — count runs face the same variable load as time runs.
- [x] **3.4** Note in a comment that the condition sequence is unseeded, so two count runs of the same N see different load sequences. Seeding is out of scope here; flag it as a follow-up if runs need to be paired.

---

## Phase 4 — Count the crossings

- [x] **4.1** In [models/vehicle.py:391-399](../models/vehicle.py#L391-L399), increment the counter next to the existing log call:
  ```python
  self.crossed = 1
  state.vehicles_crossed += 1
  log_vehicle(self)
  ```
  One line, main thread only, both modes (harmless in time mode — nothing reads it there).
- [x] **4.2** Do not touch `state.vehicles[dir]['crossed']`; it is dead and stays dead.

---

## Phase 5 — Termination in `main.py`

In [main.py:65-96](../main.py#L65-L96).

- [x] **5.1** Extract the stop decision into a helper so the frame loop stays readable:
  ```python
  def should_stop(elapsed):
      if state.run_mode == 'vehicles':
          if (state.vehicles_generated >= state.target_vehicle_count
                  and state.vehicles_crossed >= state.target_vehicle_count):
              return 'target_reached'
          if elapsed >= state.count_mode_timeout:
              return 'timeout'
          return None
      return 'duration' if elapsed >= state.duration else None
  ```
- [x] **5.2** Write a `shutdown(reason, elapsed)` that sets `state.stop_reason`, sets `state.running = False`, writes the meta sidecar in count mode, prints a one-line summary, then `pygame.quit()` / `sys.exit()`.
- [x] **5.3** Give count mode a short drain before quitting — keep rendering for ~1.5 s after the target is hit so in-flight turns finish on screen. Purely cosmetic; every vehicle is already logged. Make it a named constant, not a magic number.
- [x] **5.4** Route the `pygame.QUIT` event through `shutdown('user_quit', elapsed)` too, so a manually closed window also sets `state.running = False` and leaves a meta file behind instead of dying silently.
- [x] **5.5** Print the run mode and target at startup so a terminal full of parallel runs is readable.
- [x] **5.6** Keep `state.duration` in the `init_logger(...)` call signature — in count mode the argument is ignored by the branch in Step 2.3.

---

## Phase 6 — Batch runner and optional CLI *(optional)*

- [x] **6.1** `run_simulation.py`: nothing required — it spawns `main.py`, which reads `state.py`. Confirmed: `proc.wait()` returns cleanly for count runs (verified in 8.8).
- [ ] **6.2** *Optional:* add `argparse` to `main.py` — `--run-mode`, `--duration`, `--vehicles`, `--controller`, `--uneven` — each defaulting to the current `state.py` value and overwriting the `state` attribute before `start_simulation_threads()`. Zero-argument `python3 main.py` must behave exactly as it does today.
- [ ] **6.3** *Optional, depends on 6.2:* let `run_simulations()` take those settings and pass them through, so a batch of both arms can be launched without editing files between runs.

---

## Phase 7 — Analyzer for count logs

- [x] **7.1** Add `analyzers/analyze_count_log.py` — a copy of `analyze_log.py` with `LOG_ROOT = data/logs_by_count`, `SUMMARY_DIR = data/summary_count_logs`, and the label built as `{mode}_{uneven_mode}_n{N}`.
- [x] **7.2** Merge the meta sidecars into the summary: add `duration_sec`, `stop_reason`, and `vehicles_generated` columns, and **exclude any run whose `stop_reason` is `timeout`** from the pooled statistics — record it in the output but never average it in.
- [x] **7.3** Add a completeness assertion: `total_vehicles == target N` per file. Anything less means the run was truncated or a vehicle wedged; print it loudly.
- [x] **7.4** Do not edit `analyze_log.py`, `analyze_signal_log.py`, or `analyze_first_n_vehicles.py` at all.
- [x] **7.5** No `.gitignore` change needed — `data/*` is already ignored ([.gitignore:105](../.gitignore#L105)), so the new roots are covered.

---

## Phase 8 — Verification

All run headless (`SDL_VIDEODRIVER=dummy`). `data/logs` and `data/log_signals` were snapshotted before any edit and diffed after.

| # | Check | Result |
|---|---|---|
| 8.1 | Time mode untouched — path, filename, CSV header | ✅ `data/logs/even/45/fixed_log_45_{ts}.csv` + `data/log_signals/even/45/..._signal.csv`; header byte-identical |
| 8.2 | Count mode terminates on its own | ✅ `target_reached`, 50/50 crossed in 48.6 s |
| 8.3 | Completeness — exactly N data rows | ✅ 50 rows for N=50; 40 for N=40; 30 for both N=30 batch runs |
| 8.4 | Isolation — nothing new under the time-mode roots | ✅ `diff` against the snapshot: identical |
| 8.5 | Analyzer isolation — `analyze_log.py` unchanged | ✅ every pre-existing label byte-identical; zero count runs in the summary |
| 8.6 | Safety timeout | ✅ N=500 / timeout=20 s aborted at 20.0 s, `stop_reason: "timeout"`, sidecar recorded the partial 13/500 |
| 8.7 | Signal log lands in the count root | ✅ `data/log_signals_by_count/even/50/..._signal.csv`, header `timestamp,direction` |
| 8.8 | Batch via `run_simulation.py` | ✅ 2 instances, both exited, no filename collision, 30/30 each |
| 8.9 | Both controllers | ✅ `priority` 50/50 in 48.6 s; `fixed` 40/40 in 157.3 s |

Two observations from the test runs, worth keeping in mind when the real experiment is designed:

- **Duration is a live metric.** `fixed` needed 157 s to clear 40 vehicles; `priority` cleared 50 in 49 s. With N fixed, elapsed time *is* the throughput result — that is what count mode buys.
- **Run-to-run spread is large.** The two identical N=30 batch runs took 45.4 s and 88.6 s. The unseeded traffic-condition sequence dominates, so pairwise comparisons will need many runs per arm.

All test output was deleted afterwards; `data/logs` and `data/log_signals` are byte-identical to the pre-implementation baseline, and `data/logs_by_count`, `data/log_signals_by_count`, `data/summary_count_logs` are removed (they are recreated on the first real count run).

## Phase 9 — Documentation

- [x] **9.1** Update [ARCHITECTURE.md](ARCHITECTURE.md) §6, §7, §10, §11, §12 to describe both run modes.
- [x] **9.2** Update `README.md` with how to pick a run mode.
- [x] **9.3** Record in this file what was actually built where it diverged from the plan — see below.

### Deviations from the plan

1. **Phase 6.2/6.3 (CLI flags) not built.** Count mode is selected the same way every other setting in this project is selected: by editing `state.py`. Adding `argparse` would have introduced a second, competing configuration path for one feature only. It stays on the list as a future change if batch runs start needing per-run settings.
2. **`init_logger` now creates the signal-log directory up front** rather than lazily at the first signal change. Same end state, one less thing depending on write order.
3. **The `str.replace`-derived signal path was removed, not extended** (Step 2.2) — it would have mangled `logs_by_count` into `log_signals_by_count` by accident rather than by design, and it corrupts any absolute path containing `logs`.
4. **`analyze_count_log.py` reports throughput** (`average_vehicles_per_sec`) and `average_duration_sec`, which `analyze_log.py` has no equivalent of — with N fixed, those are the comparison that matters.

---

## Files touched

| File | Change | Risk |
|---|---|---|
| [state.py](../state.py) | +6 settings/counters | none — additive |
| [utils/logger.py](../utils/logger.py) | path branch, second global, meta writer | **highest** — shared by both modes; guarded by 8.1 |
| [core/generator.py](../core/generator.py) | quota guard + counter | low |
| [models/vehicle.py](../models/vehicle.py) | +1 line | low |
| [main.py](../main.py) | termination logic, shutdown, drain | medium |
| `analyzers/analyze_count_log.py` | new file | none — new |
| `run_simulation.py`, CLI | optional | low |

Nothing in `config.py`, the three cycle controllers, `utils/counters.py`, `utils/draw.py`, or the existing analyzers needs to change. Controller behaviour is identical in both modes by design — the run mode decides only when to stop and where to write.
