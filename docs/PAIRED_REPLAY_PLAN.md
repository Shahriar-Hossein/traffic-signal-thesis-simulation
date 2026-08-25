# Modification Plan — Paired Replay Runs (one vehicle stream, two controllers)

**Status: planned only. Nothing in this document is implemented yet (25 August 2026).**

**Goal:** produce the *same* vehicle stream twice and let a different signal controller face it each time, so the difference in the results is attributable to the controller and not to the traffic.

| Run type | Vehicles come from | Ends when | Log root |
|---|---|---|---|
| `time` *(exists)* | live random generator | wall clock reaches `duration` | `data/logs/`, `data/log_signals/` |
| `vehicles` *(exists)* | live random generator | all `N` generated vehicles crossed | `data/logs_by_count/`, `data/log_signals_by_count/` |
| **paired replay** *(new)* | a **plan file** written before the runs | the plan's `N` vehicles have crossed | `data/paired/` |

**Hard requirement, same as last time:** no file path, filename, CSV column, or row produced by a `time` or `vehicles` run may change, and no paired-run file may land where [analyze_log.py](../analyzers/analyze_log.py), [analyze_signal_log.py](../analyzers/analyze_signal_log.py), [analyze_count_log.py](../analyzers/analyze_count_log.py) or the `first_n` analyzers will find it. Background for every code reference below is in [ARCHITECTURE.md](ARCHITECTURE.md); the count-mode work this builds on is in [RUN_MODE_VEHICLE_COUNT_PLAN.md](RUN_MODE_VEHICLE_COUNT_PLAN.md).

---

## 0. Why this is worth building

Today a "fixed vs priority" comparison is two runs that faced **different traffic**. Every one of these draws is unseeded and independent per run:

| Draw | Where |
|---|---|
| traffic condition sequence (`high`/`medium`/`low`) | [generator.py:18](../core/generator.py#L18), switched on a wall clock at [generator.py:56](../core/generator.py#L56) |
| vehicle type | [generator.py:66](../core/generator.py#L66) |
| direction | [generator.py:111](../core/generator.py#L111) |
| lane | [generator.py:115](../core/generator.py#L115) |
| whether the vehicle turns | [vehicle.py:44](../models/vehicle.py#L44) |
| which lane it turns into | [vehicle.py:47](../models/vehicle.py#L47) |

The measured effect of that: **two identical N=30 count runs took 45 s and 89 s.** The load sequence moves the headline number by more than the controller plausibly does, so an unpaired comparison needs a lot of runs before the controller signal rises out of the traffic noise ([ARCHITECTURE.md §13.8](ARCHITECTURE.md)).

A shared plan removes that variance in two ways:

1. **Same input, so the output difference is the controller.** Both arms see the same N, the same arrival times, the same mix, the same turn decisions.
2. **Per-vehicle pairing becomes legitimate.** Vehicle `seq = 214` in the fixed arm and `seq = 214` in the priority arm are *the same arrival* — same type, same direction, same lane, same release offset, same turn. Their two wait times form a matched pair, so a paired test (Wilcoxon signed-rank / paired *t*) applies. That is a much stronger claim than comparing two independent means, and it typically needs ~10 plans where the unpaired design needs ~50 runs.

There is also a presentation benefit: the plan file is a data artefact you can publish alongside the thesis. "Here is the exact traffic both algorithms faced" is a reviewable claim; "both were random" is not.

---

## 1. Two ways to get "the same generation" — and why the plan file wins

### Option A — seed the RNG and re-run
Set `random.seed(k)` at the top of the generator and run twice.

Rejected. It does not actually reproduce the stream:

- **The condition switch is wall-clock driven** ([generator.py:56](../core/generator.py#L56) compares `time.time()` against `trafficConditionInterval`). The number of loop iterations before a switch depends on how fast the process actually ran, so the switch lands on a different iteration in each run, the extra/missing `random.choice` shifts the whole draw sequence, and every vehicle after that point differs. Seeding does not survive a timing difference.
- **Release times still drift.** `time.sleep(1/rate)` ([generator.py:128](../core/generator.py#L128)) is a lower bound, and the drift accumulates differently in each run.
- **The global `random` module is shared** by the generator and by `Vehicle.__init__` ([vehicle.py:44](../models/vehicle.py#L44)). This is deterministic today only because both happen on the generator thread; any future draw from another thread silently breaks reproducibility with no error.

Seeding is worth doing anyway (it makes the *plan* reproducible), but it is not sufficient on its own.

### Option B — dry run → plan file → replay *(chosen)*
Sample the stream once, write it to a file, then have the generator read that file instead of drawing. The plan is explicit, inspectable, versionable, and immune to thread timing and to later code edits. It also lets us fix the turn decisions, which live inside the vehicle constructor and are not reachable from the generator at all.

### Sub-decision: is the "dry run" a real simulation or paper generation?

| | Real dry run (pygame, recording generator) | Paper generation (pure function, no pygame) |
|---|---|---|
| Time to produce a plan | as long as a run — minutes | milliseconds |
| Captures real sleep drift | yes | no (it writes *intended* offsets) |
| Needs a display / renderer | yes | no |
| Can produce 50 plans for a batch | painful | trivial |

**Recommendation: paper generation.** The drift a real dry run would capture is not a property of the traffic, it is a property of the machine on that day — and it would be re-imposed with *different* drift on both replays anyway. What matters is that both arms get the same intended schedule and that we measure how well each arm honoured it (§3).

**Guard against drift between the two samplers:** extract the sampling logic into one function (`sample_vehicle(uneven_mode, rng)`) used by *both* the live random generator and the plan writer. If the two ever diverge, plans stop describing the same distribution the live mode produces, and nobody would notice.

---

## 2. The plan file

One file per plan, `data/paired/{plan_id}/plan.json`, JSON so the header and records travel together.

```jsonc
{
  "header": {
    "plan_id": "even_500_seed07",
    "seed": 7,
    "target_vehicle_count": 500,
    "uneven_mode": "even",
    "turn_probability": 0.5,
    "traffic_conditions": {"high": 4, "medium": 2, "low": 0.5},
    "traffic_condition_interval": 120,
    "git_rev": "c0e7bed",
    "created_at": "2026-08-25 14:02:11",
    "schema_version": 1
  },
  "condition_timeline": [
    {"t_offset_sec": 0.0,   "condition": "medium"},
    {"t_offset_sec": 120.0, "condition": "high"}
  ],
  "vehicles": [
    {"seq": 0, "t_offset_sec": 0.0,  "direction": "down", "lane": 1,
     "vehicle_type": "car", "will_turn": false, "turn_direction": "down",
     "target_turn_lane": 0, "condition": "medium"}
  ]
}
```

Notes on the schema:

- **`t_offset_sec` is relative to the start of the run**, not absolute — the same plan replays at any time of day.
- **`seq` is the pairing key.** It has to exist because `id(vehicle)` is reused by CPython after a despawn and is not a stable identifier ([ARCHITECTURE.md §13.4](ARCHITECTURE.md)); pairing on it would silently mismatch vehicles.
- **`condition` is denormalised onto each record** so an analyzer can slice by load without replaying the timeline.
- **The condition timeline is computed on a simulated clock** — the plan writer advances a virtual `t` by `1/rate` per vehicle and switches condition when `t` crosses a multiple of `trafficConditionInterval`. This is exactly what the live generator does, minus the drift.
- **`schema_version`** so an old plan can be rejected loudly rather than misread.
- **What the plan deliberately does *not* contain:** stop positions, queue positions, wait times, signal states. Everything downstream of release is a *result*, and must be free to differ between arms — that is the whole point.

---

## 3. Fidelity: what is identical, what is not, and how we prove it

**Identical by construction:** vehicle count, per-vehicle type/direction/lane/turn decisions, intended release offsets, condition schedule.

**Not identical, and cannot be:**

| Source of difference | Why | Size |
|---|---|---|
| Actual release timestamps | `time.sleep` overshoots; the OS schedules the generator thread when it feels like it | ms per vehicle, accumulating |
| Frame rate | **physics runs inside the renderer** — `draw_all_vehicles` calls `vehicle.move()` ([ARCHITECTURE.md §13.1](ARCHITECTURE.md)), so a frame drop is literally a slowdown of every vehicle | potentially seconds over a run |
| Queue geometry at release | a vehicle's initial `stop` depends on who is already in the lane ([vehicle.py:76-99](../models/vehicle.py#L76-L99)) | a legitimate controller effect, not a defect |

Two rules follow, and both are load-bearing:

1. **Run the arms sequentially, never in parallel.** Two pygame processes competing for CPU and GPU will not get the same frame rate, and since physics is in the renderer, the arm that renders slower has *slower vehicles*. That is a confound that looks exactly like a controller effect. The existing [run_simulation.py](../run_simulation.py) parallel pattern must not be reused here.
2. **Measure adherence and gate on it.** Each arm records, in its `_meta.json`:
   - `release_drift_mean_ms`, `release_drift_max_ms` (actual release time minus planned offset),
   - `fps_mean`, `fps_min`, `frames_total`,
   - `vehicles_planned`, `vehicles_released`, `vehicles_crossed`.

   The comparison step then refuses to report a pair whose arms differ in `fps_mean` by more than a set tolerance (start at 5%) or whose `release_drift_max_ms` exceeds a threshold (start at 250 ms). A pair that fails the gate is recorded as invalid rather than quietly averaged in. Without this check the whole design rests on an assumption nobody verified.

---

## 4. How it wires into the existing switches

Keep the new switch **orthogonal** to `run_mode` rather than adding a third value to it:

```python
# state.py
# where vehicles come from: 'random' (live draws) or 'plan' (replay a plan file)
generation_source = 'random'
vehicle_plan_path = None   # set when generation_source == 'plan'

# paired-run identity (only set by the driver script)
pair_id   = None    # e.g. 'even_500_seed07'
arm_label = None    # e.g. 'fixed' / 'priority'
```

A replay run is `run_mode = 'vehicles'` + `generation_source = 'plan'`. Termination logic is untouched: the plan defines N, `target_vehicle_count` is set from the plan header at load time, and [main.should_stop](../main.py#L52) already ends the run when N have crossed. The safety timeout stays and still matters more here than anywhere else — a wedged vehicle in arm B wastes arm A's run too.

**A CLI is now unavoidable.** Count mode could stay hand-edited in [state.py](../state.py); a paired run cannot, because the driver has to launch two processes with different controllers and the same plan. This is where Phase 6 of the previous plan finally has to happen — but minimally:

```
python3 main.py --plan data/paired/even_500_seed07/plan.json \
                --controller fixed --pair-id even_500_seed07 --arm fixed
```

Every flag defaults to the current `state.py` value, so running `python3 main.py` with no arguments behaves exactly as it does today. That is the regression test for Phase 5.

---

## 5. Log layout

```
data/paired/
  {plan_id}/
    plan.json
    fixed/
      fixed_pairlog_{N}_{ts}.csv
      fixed_pairlog_{N}_{ts}_signal.csv
      fixed_pairlog_{N}_{ts}_meta.json
    priority/
      priority_pairlog_{N}_{ts}.csv
      ...
    comparison.json
```

- A **third root**, sibling to `logs/` and `logs_by_count/`, for the same reason count mode got its own: every analyzer rebuilds a run's identity positionally from the folder path ([ARCHITECTURE.md §11](ARCHITECTURE.md)), and a paired run does not fit either existing shape.
- The arm folder holds the controller name, so `parts[-2]` still yields something meaningful, and the filename token `pairlog` marks a file as paired even after it is copied elsewhere. `filename.split("_")[0]` still gives the controller.
- **Vehicle CSV = the existing six columns plus `plan_seq` appended last.** Appending rather than inserting means the first six columns still parse positionally if a file ever ends up in front of an old analyzer. It should not, but cheap insurance.
- `comparison.json` is written by the driver/analyzer, never by the simulation.

---

## Phase 1 — Extract the sampler *(no behaviour change)*

- [ ] **1.1** Move the direction-weight table and the type/lane/direction draws out of `generateVehicles` into `sample_vehicle(uneven_mode, rng)` returning a dict, in a new `core/plan.py` (or `core/sampling.py`).
- [ ] **1.2** `generateVehicles` calls it with `rng = random` — identical behaviour, same draw order.
- [ ] **1.3** Move the turn decision out of `Vehicle.__init__` into `sample_turn(direction, lane, rng)` so the plan writer can make the same decision the constructor would.
- [ ] **1.4** Verify: with a fixed seed, `sample_vehicle` called 1000 times reproduces the same sequence as the old inline code with the same seed. This is the only phase where a before/after equivalence test is possible — do it here or lose the ability.

## Phase 2 — Plan writer

- [ ] **2.1** `scripts/make_plan.py --seed 7 --count 500 --uneven-mode even --out data/paired/{plan_id}/plan.json`.
- [ ] **2.2** Uses `random.Random(seed)` — a private instance, never the global module, so it cannot be perturbed by anything else.
- [ ] **2.3** Advances a virtual clock by `1/trafficConditions[condition]` per vehicle and switches condition on the `trafficConditionInterval` boundary, mirroring [generator.py:56](../core/generator.py#L56).
- [ ] **2.4** Writes the header (including `git_rev` and the config snapshot) and the records.
- [ ] **2.5** Deterministic: same seed + same count + same mode ⇒ byte-identical file. Test it.
- [ ] **2.6** `--plans 10` convenience flag to emit a whole batch of seeds at once.

## Phase 3 — Vehicle accepts injected decisions

- [ ] **3.1** Add optional keyword args to `Vehicle.__init__`: `will_turn=None, turn_direction=None, target_turn_lane=None`.
- [ ] **3.2** When they are `None` (the default), draw exactly as today — the random path must not change at all.
- [ ] **3.3** When supplied, skip the draws and use the given values, then compute `turn_total_frames` and `_dynamic_trigger_offset` from them as usual.

## Phase 4 — Replay generator

- [ ] **4.1** `replay_vehicles(plan)` in [core/generator.py](../core/generator.py), selected when `state.generation_source == 'plan'`.
- [ ] **4.2** Loop over records; for each, sleep until `run_start + t_offset_sec` (absolute deadline against a monotonic clock, **not** cumulative `sleep(delta)` — cumulative sleeps let drift compound, deadline sleeps let it self-correct).
- [ ] **4.3** If already past the deadline, release immediately and accumulate the lateness into the drift stats rather than trying to catch up by skipping.
- [ ] **4.4** Set `state.traffic_condition` from the record so the on-screen/logged condition stays meaningful.
- [ ] **4.5** Respect `state.running` so a `user_quit` still stops the thread.
- [ ] **4.6** Record `release_drift_*` into module state for the meta sidecar.

## Phase 5 — State + CLI wiring

- [ ] **5.1** Add `generation_source`, `vehicle_plan_path`, `pair_id`, `arm_label` to [state.py](../state.py) with today's behaviour as the default.
- [ ] **5.2** `argparse` in [main.py](../main.py): `--plan`, `--controller`, `--pair-id`, `--arm`, `--run-mode`, `--count`, `--uneven-mode`. Each defaults to the current `state.py` value.
- [ ] **5.3** When `--plan` is given: load it, validate `schema_version`, set `target_vehicle_count` from the header, and **fail loudly** if the plan's `uneven_mode` / `turn_probability` / condition table disagrees with the current [config.py](../config.py) — a plan replayed against changed config is a silently invalid comparison.
- [ ] **5.4** Track FPS in the frame loop (frame counter + elapsed) for the meta sidecar.

## Phase 6 — Logger: paired destination

- [ ] **6.1** In `init_logger`, when `state.pair_id` is set, write to `data/paired/{pair_id}/{arm_label}/` with the `pairlog` token.
- [ ] **6.2** Add `plan_seq` as the seventh CSV column, populated from the vehicle's plan record (`None`/blank in non-paired modes — which never reach this branch anyway).
- [ ] **6.3** Extend `write_run_meta` with `plan_id`, `arm`, `controller`, `vehicles_planned`, `vehicles_released`, `release_drift_mean_ms`, `release_drift_max_ms`, `fps_mean`, `fps_min`.
- [ ] **6.4** Confirm the sidecar is written before `sys.exit()` — `shutdown()` already does this, but the shutdown path has no thread join and no flush barrier ([ARCHITECTURE.md §13.6](ARCHITECTURE.md)), so anything new must be written on the main thread inside `shutdown`, not from the generator.

## Phase 7 — The driver

- [ ] **7.1** `run_paired.py --plan <path> --arms fixed priority`.
- [ ] **7.2** Generates the plan first if given `--seed` instead of `--plan`.
- [ ] **7.3** Runs each arm as a **sequential** subprocess (`Popen` + `wait`), never concurrently (§3).
- [ ] **7.4** Fails the pair if any arm exits non-zero or ends with `stop_reason != 'target_reached'`.
- [ ] **7.5** Calls the analyzer and writes `comparison.json`.
- [ ] **7.6** `--plans <dir>` to sweep a batch of plans and emit an aggregate across pairs.
- [ ] **7.7** Design for **K arms, not 2**, from the start — `fairness_priority` already exists in [initializer.py](../core/initializer.py) and will want to be a third arm. The cost of a list instead of a pair is near zero now and a rewrite later.

## Phase 8 — Paired analyzer

- [ ] **8.1** `analyzers/analyze_paired.py`, reading one `{plan_id}/` folder.
- [ ] **8.2** Validity gate first: both arms complete, both crossed `N`, FPS and drift within tolerance. Report invalid pairs as invalid — never drop them silently.
- [ ] **8.3** Per-arm summary: total duration, mean / median / p90 / max wait, throughput (veh/min), per-direction and per-type means, signal switch count from the signal log.
- [ ] **8.4** Paired section: join the two arms on `plan_seq`, compute per-vehicle Δwait, report mean Δ, median Δ, win rate (% of vehicles better off under each arm), and a signed-rank test.
- [ ] **8.5** Flag any `plan_seq` present in one arm and missing from the other — that means a vehicle never crossed, and it invalidates the pairing for that row.
- [ ] **8.6** Batch mode: aggregate across plans, one row per plan plus an overall paired test.

## Phase 9 — Verification

- [ ] **9.1** **Regression, non-negotiable:** a `time` run and a `vehicles` run before and after the change produce identical folder paths, filenames, headers, and column counts; `analyze_log.py` and `analyze_count_log.py` output is unchanged. (Compare against a saved baseline the way the count-mode work did.)
- [ ] **9.2** `python3 main.py` with no arguments still runs exactly as today.
- [ ] **9.3** Same seed ⇒ byte-identical plan file, twice.
- [ ] **9.4** Both arms release the same N with the same `plan_seq` set; diff the `(plan_seq, direction, lane, vehicle_type)` projection of the two CSVs — it must match exactly.
- [ ] **9.5** Drift and FPS within tolerance on the target machine at N=500; if not, lower N or go headless before generating real data.
- [ ] **9.6** Sanity check the effect direction: a small pilot (3 plans, N=100) should reproduce the known ordering from the count-mode pilot rather than reversing it.
- [ ] **9.7** Delete pilot data before generating the real dataset.

## Phase 10 — Documentation

- [ ] **10.1** README section on paired runs with the two commands.
- [ ] **10.2** ARCHITECTURE.md: new generation source, third log root, new meta fields, updated fragile-points list.
- [ ] **10.3** Record in this file what was actually built vs. planned, as the previous plan does.

---

## What `comparison.json` should hold

```jsonc
{
  "plan_id": "even_500_seed07",
  "valid": true,
  "invalid_reasons": [],
  "arms": {
    "fixed":    {"duration_sec": 412.3, "wait_mean": 18.4, "wait_p90": 41.2, "throughput_per_min": 72.8},
    "priority": {"duration_sec": 331.7, "wait_mean": 12.1, "wait_p90": 27.5, "throughput_per_min": 90.4}
  },
  "paired": {
    "n_matched": 500,
    "delta_wait_mean": -6.3,
    "delta_wait_median": -4.8,
    "win_rate_priority": 0.78,
    "wilcoxon_p": 0.0001
  }
}
```

The per-arm block is what the current analyzers already give you. The `paired` block is the part that only exists because of this design, and it is the part worth putting in the thesis.

---

## Decisions still open

1. **Plan source** — paper generation (recommended) vs. recorded dry run.
2. **Batch size** — how many plans per configuration. Recommend ≥10 seeds per `uneven_mode`, which the paired design makes sufficient.
3. **Arms** — two (`fixed`, `priority`) or three (`+ fairness_priority`). Build for K either way (7.7).
4. **Headless replay** (`SDL_VIDEODRIVER=dummy`) to cut render variance. Tempting, but physics lives in the renderer, so this changes the frame rate rather than removing it from the equation — only adopt it if 9.5 shows it makes FPS *more* stable, and never mix headless and windowed runs within a pair.
5. **Tolerances** for the §3 validity gate — 5% FPS / 250 ms drift are starting guesses, to be set from what 9.5 actually measures.

---

## Fragile points this touches

Cross-referenced to [ARCHITECTURE.md §13](ARCHITECTURE.md):

| # | Fragile point | Effect here |
|---|---|---|
| 1 | Physics inside the renderer | The main threat to validity. Handled by sequential arms + the FPS gate (§3). |
| 2 | `log_filename` is a module global — one run per process | Fine: each arm is its own process. Do not try to run both arms in one process. |
| 3 | Folder path is the only run metadata | Getting worse, so paired runs add a real `_meta.json` and stop leaning on the path. |
| 4 | `id(vehicle)` is not unique | Directly fatal to pairing — hence the `plan_seq` column. |
| 6 | `sys.exit()` with no join or flush | New meta fields must be computed on the main thread before `shutdown` returns. |
| 7 | The folder bucket means different things per mode | A third root makes this worse; the `_meta.json` is the mitigation. |
| 8 | Unseeded condition sequence | This plan is the fix for it, for paired runs at least. |

---

## Files that would be touched

New: `core/plan.py`, `scripts/make_plan.py`, `run_paired.py`, `analyzers/analyze_paired.py`.
Changed: [state.py](../state.py), [core/generator.py](../core/generator.py), [models/vehicle.py](../models/vehicle.py), [main.py](../main.py), [utils/logger.py](../utils/logger.py), [README.md](../README.md), [docs/ARCHITECTURE.md](ARCHITECTURE.md).
Untouched: every existing analyzer, `data/logs*`, `data/log_signals*`.
