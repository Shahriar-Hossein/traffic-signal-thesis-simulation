# Variable-Load Pilot — Priority vs Fixed at 600 s

**Run:** 25 August 2026, 00:39 (fixed) and 00:46 (priority) — 5 runs per arm, 600 s each, `uneven_mode = 'even'`.
**Data:** `data/logs/even/600/{fixed,priority}_log_600_20260825_*.csv` (10 files, 11,784 crossing records).
**Change under test:** vehicle generation is no longer a constant 5 veh/s burst. It now switches every 2 minutes between three traffic conditions, chosen at random.
**Relation to the review:** this is a first, small step toward [§6.2 of the improvement plan](THESIS_IMPROVEMENT_PLAN.md) ("only one demand regime, and it is the wrong one"). It is a pilot, not the experiment that plan asks for — see §7 and §8 below.

---

## 0. Verdict

**Priority did not perform worse. It performed better on delay at every load level measured, and its capacity is unchanged.**

The number that looks like a loss — priority crossed 5,585 vehicles against fixed's 6,199 — is an artefact of the new generator. Each run now draws its own random sequence of high/medium/low phases, so the ten runs did not face the same demand. Peak throughput is identical between arms (189 vs 190 crossings/min), which is what settles it: the two controllers discharge traffic at the same rate, exactly as [§1.1 of the improvement plan](THESIS_IMPROVEMENT_PLAN.md) found for the constant-load dataset. Priority simply drew lighter traffic.

The delay advantage is real but this pilot is underpowered to size it: *p* = 0.045 on 5 runs per arm, with run-to-run variance an order of magnitude larger than in the constant-load dataset.

---

## 1. What was changed

Generation rate is now driven by a randomly selected traffic condition that switches on a fixed interval.

| Condition | Rate | Inter-arrival sleep |
|---|---|---|
| `high` | 4 veh/s | 0.25 s |
| `medium` | 2 veh/s | 0.5 s |
| `low` | 0.5 veh/s | 2 s |

Defined in [config.py:162-169](../config.py#L162-L169); switching logic in [core/generator.py:41-47](../core/generator.py#L41-L47); the active condition is exposed as [state.traffic_condition](../state.py#L39).

Three things about the implementation matter for reading the results:

1. **The switch interval is 120 s**, so a 600 s run contains exactly 5 phases.
2. **`pick_traffic_condition` never repeats the current condition** ([core/generator.py:12-18](../core/generator.py#L12-L18)). Consecutive phases always differ; the sequence is a random walk on 3 states, not 5 iid draws.
3. **Arrivals are still deterministic within a phase** — a fixed sleep, not a Poisson process. [§3.5 of the improvement plan](THESIS_IMPROVEMENT_PLAN.md) is unaddressed by this change; the load is now piecewise-constant rather than constant, which is a different thing from stochastic.

The old pacing (`cnt % 5 == 0 → sleep(1)`, i.e. 5 vehicles released simultaneously then a 1 s gap) is gone. Even the `high` phase is now both slower (4 veh/s) and smoother than the old load, so **delay figures from this run set are not comparable to any earlier dataset in `data/`.**

---

## 2. Headline results

Pooled over 5 runs per arm, all logged crossings:

| Metric | priority | fixed | Difference |
|---|---|---|---|
| Vehicles crossed | 5,585 | 6,199 | −9.9% *(load artefact — see §3)* |
| Mean wait | **35.2 s** | 45.0 s | **−21.7%** |
| Median wait | **29.1 s** | 44.6 s | **−34.8%** |
| p90 wait | **80.7 s** | 88.8 s | −9.1% |
| Max wait | **119.9 s** | 127.6 s | −6.1% |
| Crossed with zero wait | 7.4% | 9.2% | +1.8 pp (fixed) |
| Peak throughput | 189/min | 190/min | ±0 |

Per run:

| File | Crossed | Mean | Median | p90 | Max |
|---|---|---|---|---|---|
| `priority_...004630` | 1,126 | 36.95 | 31.62 | 81.35 | 94.54 |
| `priority_...004631` | 1,033 | 33.25 | 26.72 | 77.83 | 108.92 |
| `priority_...004633` | 1,299 | 43.85 | 41.62 | 87.34 | 105.53 |
| `priority_...004634` | 1,250 | 36.20 | 31.14 | 81.24 | 119.86 |
| `priority_...004636` | 877 | 21.12 | 17.62 | 47.34 | 84.13 |
| `fixed_...003903` | 1,251 | 43.32 | 40.99 | 87.58 | 110.59 |
| `fixed_...003904` | 953 | 43.14 | 43.20 | 86.27 | 117.92 |
| `fixed_...003906` | 1,368 | 48.71 | 49.59 | 90.84 | 127.63 |
| `fixed_...003907` | 1,259 | 42.24 | 41.45 | 86.34 | 120.80 |
| `fixed_...003909` | 1,368 | 46.50 | 46.76 | 89.48 | 127.17 |

The spread of the *priority* run means (21.1 s to 43.9 s) is the random condition sequence showing through, not controller instability.

---

## 3. Why the crossing counts are not a finding

Total crossings per run is now a measurement of **which conditions that run happened to draw**, not of controller capacity. Nothing in the logs records the drawn sequence — `state.traffic_condition` is set but never written to the CSV — so the sequences cannot be recovered post hoc. This is the single biggest defect in the pilot.

Two pieces of evidence that the count gap is demand, not performance:

- **Peak throughput is equal.** Best 60 s window: priority 189, fixed 190. Mean of the top 5 windows: priority 180, fixed 189. Both arms saturate at ~3.2 veh/s.
- **The low outlier is internally consistent.** `priority_...004636` crossed only 877 vehicles *and* had by far the lowest delay (21.1 s mean, 47.3 s p90). Low throughput with low delay is the signature of light demand. A controller that was actually failing would show low throughput with *high* delay.

---

## 4. Load-controlled comparison

Since offered load is unrecorded, the closest available control is to bucket every run-minute by its own crossing count and compare delay within buckets. Pooled across all 10 runs, 100 run-minutes:

| Crossings in that minute | priority | fixed | Gap |
|---|---|---|---|
| <60/min | 14.7 s *(11 min)* | 25.8 s *(8 min)* | −11.1 s |
| 60–120/min | 30.3 s *(14 min)* | 37.4 s *(15 min)* | −7.1 s |
| 120–160/min | 31.1 s *(11 min)* | 47.3 s *(10 min)* | −16.2 s |
| 160+/min | 43.3 s *(14 min)* | 49.5 s *(17 min)* | −6.2 s |

Priority is ahead in every bucket. The gap is widest in the middle of the range and narrows at saturation — consistent with the mechanism: the controller earns its advantage by moving green away from empty approaches, and at 160+/min there are no empty approaches left to harvest. This is the first evidence in the project that the adaptive mechanism does something at low demand, which the constant-oversaturation dataset could not show ([§1.2](THESIS_IMPROVEMENT_PLAN.md) found the green cap binding 71–95% of the time).

**Caveat:** crossings/min is *throughput*, and under saturation throughput plateaus regardless of demand. So the 160+ bucket mixes "moderately busy" with "hopelessly overloaded" minutes, and the buckets are not independent samples (minutes within a run are correlated). Treat this table as directional, not as a controlled experiment.

---

## 5. Directional equity

Pooled per approach:

| Approach | priority mean | fixed mean |
|---|---|---|
| right | 35.8 s | 49.7 s |
| down | 36.0 s | 39.7 s |
| left | 32.3 s | 42.4 s |
| up | 36.7 s | 47.7 s |
| **spread (max−min)** | **4.5 s** | **10.0 s** |

Priority's share of crossings by approach is 24.4 / 25.2 / 24.5 / 25.8 % — flat. It is not buying its average by starving an approach; it is both faster *and* more even. This reproduces the equity result that [§7.4 of the improvement plan](THESIS_IMPROVEMENT_PLAN.md) identifies as the strongest unreported finding in the project, now under variable load.

---

## 6. Within-run behaviour

Mean wait per 60 s bucket climbs through nearly every run (typically 12–20 s in minute 1 to 45–70 s by minute 10), and crossings/min plateaus at 170–190. Interpretation: the `high` phase offers 4 veh/s against a discharge capacity of ~3.2 veh/s, so every high phase builds a queue that the following medium/low phase only partly drains. Delay is therefore still partly a function of run length rather than a property of the controller — the same objection [§6.2](THESIS_IMPROVEMENT_PLAN.md) raises about the constant-load runs, softened but not removed.

Final-2-minutes mean wait: priority 41.9 s, fixed 52.1 s.

The one run that escapes this is `priority_...004636`, which stays in the 13–33 s band throughout — a sequence with enough low phases to keep up.

---

## 7. Statistical strength

Per-run mean waits:

- priority: 36.95, 33.25, 43.85, 36.20, 21.12 → **34.27 ± 8.32 s** (CV 24.3%)
- fixed: 43.32, 43.14, 48.71, 42.24, 46.50 → **44.78 ± 2.72 s** (CV 6.1%)

Welch's *t* = 2.685, df ≈ 4.85, **two-tailed *p* = 0.045**. Difference 10.5 s (23.5%). Rank-based: 22 of 25 priority-vs-fixed run pairs favour priority.

This clears 0.05 by a hair and should not be reported as a settled result. The reason is visible in the CVs: the constant-load dataset had run-to-run CV of 0.3–0.9%, and **randomising the load raised it to 6–24%** — one to two orders of magnitude. Five runs per arm was ample under constant load and is nowhere near enough here. Under this design the required replication count goes up by roughly the square of the CV ratio.

The fix is not "run 500 replications". It is common random numbers (§8.2): pair the arms on an identical condition sequence and the load variance cancels out of the comparison entirely.

---

## 8. Limitations

### 8.1 Carried over from the existing review — unchanged by this run

- **Differential right-censoring** ([§4.1](THESIS_IMPROVEMENT_PLAN.md)). Only vehicles that cross the stop line are logged. Everything still queued at 600 s is discarded, and since the arms leave different residual queues, both means are biased low by different amounts. Applies in full here.
- **No RNG seeding** ([§4.3](THESIS_IMPROVEMENT_PLAN.md)). None of these 10 runs is reproducible.
- **`vehicle_id` is `id(vehicle)`** ([§4.2](THESIS_IMPROVEMENT_PLAN.md)). Do not compute unique-vehicle counts from these files.
- **Uncalibrated model** ([§3.4](THESIS_IMPROVEMENT_PLAN.md)). All times are simulation-seconds against a ~0.78 s saturation headway (real-world: ~2 s).

### 8.2 New, introduced by the variable-load generator

- **The condition sequence is not logged.** The independent variable of this experiment is absent from the data. Everything in §4 is a workaround for this.
- **The arms saw different demand.** Runs were sequential, arms unpaired, sequences independent. Any cross-arm total is confounded.
- **Phases are not iid.** No-repeat selection means the sequence is a Markov chain; a run cannot draw `high, high, high`. Long-run expected rate is 2.17 veh/s, but the variance of the per-run mean rate is lower than iid sampling would give.
- **Only 5 phases per run.** With 600 s runs and 120 s phases there are five draws, so per-run demand is coarse and lumpy.
- **Delay is not comparable to earlier datasets.** Different arrival rate *and* different arrival pattern.

---

## 9. Next steps, in order

1. **Log the condition.** Append a `traffic_condition` column in [utils/logger.py](../utils/logger.py#L36-L44) from `state.traffic_condition`. Appending at the end keeps existing analyzers working. Without this the whole design is unanalysable — do it before the next run.
2. **Seed for common random numbers** ([§4.3](THESIS_IMPROVEMENT_PLAN.md)). Add `--seed k`, seed the generator, record the seed in the filename, and run each arm on the same seed set. Both controllers then face a byte-identical condition sequence *and* arrival stream, the load variance in §7 cancels, and a paired test applies.
3. **Log the run-end queue** ([§4.1](THESIS_IMPROVEMENT_PLAN.md), fix 1). Snapshot every still-queued vehicle with `censored=1` at `state.running = False`.
4. **Re-run paired, ≥20 seeds per arm.** Then the §4 analysis becomes a real per-condition breakdown instead of a throughput proxy.
5. **Consider a longer horizon or shorter phases.** 5 phases per run is coarse; 1800 s runs give 15, or drop the interval to 60 s.
6. **Add the matched-cycle arm** ([§6.1](THESIS_IMPROVEMENT_PLAN.md)). Still the highest-value missing experiment, and unaffected by any of this.

---

## Appendix — reproducing these numbers

```bash
# headline table
python3 - <<'PY'
import csv, glob, statistics as st
files = sorted(glob.glob("data/logs/even/600/*_600_20260825_*.csv"))
for mode in ('priority','fixed'):
    w = [float(r['wait_time_sec'])
         for f in files if mode in f
         for r in csv.DictReader(open(f))]
    print(mode, len(w), round(st.mean(w),2), round(st.median(w),2),
          round(sorted(w)[int(.9*len(w))],2), max(w))
PY
```

Run configuration: `state.duration = 600`, `state.uneven_mode = 'even'`, `state.currentMode` set per arm, 5 concurrent instances via `python3 run_simulation.py`.
