# Thesis Improvement Plan — Publication Readiness Review

**Subject:** *A Dynamic Traffic Signal Controlling System in Vehicular Networks* (Hossein & Saima, IUBAT, Summer 2025)
**Reviewed:** 21 August 2026 — against `docs/Thesis_reported_proper_Formated.pdf`, the code in this repository, and the full 904,170-record dataset in `data/`.
**Purpose:** identify what must change in the simulation, the data collection, and the analysis for this work to survive peer review.

---

## 0. Verdict in one page

The engineering is solid, the dataset is unusually large for an undergraduate thesis (550 runs, ~86 simulated hours), and the effect is real and highly replicable (run-to-run CV 0.3–0.9%). None of that is in question.

The problem is that **the headline claim is not supported by the experiment that was run.** The thesis claims adaptivity causes the improvement. The data show the improvement is caused by a longer cycle. A competent reviewer will find this in an afternoon, and the finding is arithmetic, not opinion — §1 below reproduces it from the retained logs.

There are four distinct classes of problem, in order of severity:

| # | Problem | Severity | Fixable? |
|---|---------|----------|----------|
| 1 | The measured gain is a cycle-length effect, not an adaptivity effect. The proposed controller is pinned at its green cap 71–95% of the time, so it is functionally a fixed-time controller with a 24 s green. | **Fatal to the current claim** | Yes — one new experimental arm |
| 2 | The two "independent" metrics (delay, throughput) are mathematically the same measurement. Delay is predictable from throughput to within 0.3 percentage points. | **Fatal to the "improves on every metric" framing** | Yes — reframe + new metrics |
| 3 | Data collection defects: 36–47% of vehicles are never logged, and at a *different rate per arm*; `vehicle_id` is not unique; no RNG seeds; wall-clock timing. | **Serious** | Yes — code fixes, re-run |
| 4 | The simulation is uncalibrated and its baseline is a strawman: one approach green at a time, no startup lost time, saturation headway 0.78 s (real: ~2 s), no px→m scale. | **Serious** | Yes — model changes |

Plus one large **missed opportunity**: the strongest and most novel result in the dataset — the directional-equity finding — is not reported quantitatively anywhere in the thesis. It is announced as one of four metrics in the Chapter 4 introduction and then never given a section, table, or figure.

**The good news:** every one of these is fixable with compute you already have, and the fixed version is a *better* paper than the current one. The honest, mechanistic story ("we measured where the gain actually comes from, and it is not where everyone assumes") is more publishable than an unexamined "our method is 16% better."

---

## 1. The finding that must be confronted first

### 1.1 Both controllers discharge traffic at exactly the same rate

Computed from the retained logs (`data/logs/even/`, `data/log_signals/even/`):

| Arm | Mean phase | Green/phase | Green fraction | Total green per run | Vehicles served | **Saturation flow** |
|---|---|---|---|---|---|---|
| fixed, 300 s | 17.0 s | 12.0 s | 0.706 | 204.7 s | 787.2 | **3.85 veh/s** |
| priority, 300 s | 25.6 s | 20.6 s | 0.805 | 233.4 s | 884.8 | **3.79 veh/s** |
| fixed, 1800 s | 17.0 s | 12.0 s | 0.706 | 1263.5 s | 4933.3 | **3.90 veh/s** |
| priority, 1800 s | 28.5 s | 23.5 s | 0.825 | 1476.0 s | 5723.3 | **3.88 veh/s** |

The saturation flow — vehicles discharged per second *of green* — is **identical to within 1.5%** across both controllers and all durations. The intersection clears traffic at the same rate no matter which algorithm is running.

Therefore:

```
throughput  =  saturation flow  ×  total green time
                  (identical)        (the only difference)
```

Check it: at 1800 s the total-green ratio is 1476.0 / 1263.5 = **1.168**; the observed throughput ratio is 5723.3 / 4933.3 = **1.160**. At 300 s: 1.140 predicted, 1.124 observed. The residual (0.8–1.4%) is the early-termination rule and startup transients.

**The entire 12–16% throughput gain is bought by spending 20 s of yellow every 114 s instead of every 68 s.** A fixed-time controller retimed to a 24 s green would capture the same gain without any sensing, any RSU, any OBU, any VANET.

### 1.2 The adaptive mechanism is inactive

From the signal logs, distribution of green durations under the priority controller:

| Duration | At 6 s floor | Between floor and cap | **At 24 s cap** |
|---|---|---|---|
| 300 s | 7.2% | 21.7% | **71.1%** |
| 1800 s | 1.6% | 3.3% | **95.1%** |

The demand-proportional formula `g = ⌊0.75 · W⌋` is almost never the binding constraint. The `min()` is. The controller in [core/cycle_priority.py:60](../core/cycle_priority.py#L60) degenerates under saturation into `green_time = 24`.

The early-termination rule at [core/cycle_priority.py:67](../core/cycle_priority.py#L67) (`vc <= 3 and t >= 6`) **never fires at all** in this regime — the raw uncrossed queue on every approach is in the hundreds.

So of the three mechanisms claimed in Chapter 3, only one is actually operating: the **phase ordering**. And ordering does not affect throughput (both arms discharge at the same saturation flow) — it affects *equity*, which the thesis does not measure.

### 1.3 Delay is not a second, independent metric

In a permanently oversaturated deterministic queue, vehicle *n* arrives at *n/λ* and departs at *n/μ*, so mean delay over the vehicles actually served in a run of effective length *T* is

```
E[delay]  ≈  T/2  −  N /(2λ)          where N = vehicles served, λ = arrival rate = 5 veh/s
```

Nothing in that expression describes the algorithm. Only *N* does. Testing it against the retained data:

| Duration | Predicted Δ delay | **Observed Δ delay** |
|---|---|---|
| 300 s | −14.7% | −11.5% |
| 600 s | −17.0% | −16.2% |
| 1200 s | −18.5% | **−18.9%** |
| 1800 s | −19.7% | **−19.4%** |

At the two longest durations the prediction is accurate **to within 0.4 percentage points**, using no information about the controller other than how many vehicles it served.

**Consequence for the thesis:** Table 4.1 and Figure 4.1 are not independent evidence. They are the throughput result, re-expressed. Presenting them as two separate confirmations ("outperforms on every evaluated statistic", p. 41) is a reviewer-visible error. So is Figure 4.4, which stacks three curves that are all the same underlying quantity and reads as three independent confirmations.

---

## 2. Priority-ordered work plan

Ordered by (value to the paper) ÷ (effort). Items 1–4 are what makes it publishable; 5–9 make it strong.

| # | Work item | Effort | What it buys |
|---|---|---|---|
| 1 | **Matched-cycle baseline arm** — fixed-time with 24 s green (cycle ≈ 116 s) | ~4 h compute, 1 line of config | Resolves the fatal confound. Turns "our method is better" into a *tested* claim either way. |
| 2 | **Asymmetric-demand experiments** (`up`, `left_right`) on all arms | ~10 h compute, already implemented | Tests the mechanism the design actually targets. This is where adaptivity *should* win, and currently it is untested. |
| 3 | **Report the equity result properly** — table + figure + Jain's index | 1 day of analysis, no new runs | Recovers your genuinely novel finding from the existing data. |
| 4 | **Fix the four measurement defects** (§4) and re-run | 1 day code, re-run affected batches | Removes the "your data is biased" objection entirely. |
| 5 | **Undersaturated / near-capacity demand** (1–2.5 veh/s) | ~10 h compute | Covers the regime where most real intersections operate. |
| 6 | **Calibrate the traffic model** — startup lost time, realistic saturation headway, px→m scale | 2–3 days code + re-run | Makes absolute numbers reportable instead of dimensionless. |
| 7 | **Sensitivity sweep on the green cap** (12/18/24/30/no-cap) | ~8 h compute | Directly addresses §1.2; shows where adaptivity re-activates. |
| 8 | **Realistic phasing** (2-phase or 4-phase NEMA with paired approaches) | 3–5 days code | Removes the strawman-baseline objection. Optional but strong. |
| 9 | **Detection-zone limit** on queue counting | Half day | Makes the VANET framing physically meaningful (§5.3). |

---

## 3. Simulation model — what to change

### 3.1 The baseline phasing is a strawman *and* the proposed controller inherits it

Both controllers serve **one approach at a time** ([core/cycle_fixed.py:18](../core/cycle_fixed.py#L18), [core/cycle_priority.py:48](../core/cycle_priority.py#L48)). Real four-approach signals almost never do this. Standard practice is two phases (north–south, then east–west) or NEMA eight-phase with paired movements, because opposing through movements do not conflict and can run concurrently.

Serving approaches singly roughly **halves the intersection's capacity** and doubles the number of lost-time intervals per cycle. Both arms suffer equally, so the *comparison* is internally valid — but the absolute claim "adaptive control increases intersection capacity by 16%" is measured against a baseline no traffic engineer would deploy.

A reviewer from a transport venue will raise this immediately. Two options:

- **Cheap:** state it explicitly as a scope limitation ("single-approach phasing was modelled; results are not directly comparable to dual-ring phasing") and keep the comparison relative. Acceptable for a CS/VANET venue.
- **Strong:** implement paired phasing for both arms. This is the single change that would most improve the model's credibility, and it is the one that makes the fixed-time baseline genuinely competitive.

### 3.2 Yellow is 100% lost time — which inflates the whole effect

During yellow, [core/cycle_fixed.py:54-56](../core/cycle_fixed.py#L54-L56) and [core/cycle_priority.py:74-76](../core/cycle_priority.py#L74-L76) reset `vehicle.stop` for every uncrossed vehicle on the approach, so **discharge drops to exactly zero for the full 5 s**. In reality a substantial fraction of the yellow interval is used — the effective green is typically `green + yellow − lost time`, with total lost time per phase around 3–4 s, not 5 s.

This matters directly to your result: because the entire measured gain is a lost-time effect (§1.1), **overstating lost time overstates the gain.** If effective lost time were 3 s instead of 5 s, the fixed-time controller's lost-time share would drop from 29.4% to ~19% and the priority controller's advantage would shrink by roughly a third.

Fix: allow vehicles already within a defined distance of the stop line to continue through the yellow, and introduce a short (1–2 s) all-red clearance. This also fixes the fact that there is currently **no all-red interval at all** — the next approach goes green the instant yellow ends, while turning vehicles from the previous phase are still physically inside the intersection.

### 3.3 No startup lost time, no acceleration

Vehicles move at full free-flow speed from a standing start on the first frame of green. Real queues discharge with 2–3 s of startup lost time and progressively falling headways for the first four to six vehicles.

Because startup loss is a *per-phase* penalty, adding it would **increase** the advantage of the longer-cycle controller — so modelling it honestly likely helps your result. That is a good reason to do it: a correction that could have gone against you and didn't is worth much more than an uncorrected model.

### 3.4 The model is uncalibrated and dimensionless

Speeds are in px/frame with no stated px→m conversion ([config.py:7-12](../config.py#L7-L12)). Back out the implied saturation headway from the data: 3.85 veh/s across 3 lanes = **0.78 s per lane** — roughly 4,600 veh/h/lane. Field saturation flow is ~1,900 veh/h/lane (headway ≈ 1.9 s). **The simulated intersection discharges about 2.4× faster than any real one.**

Consequences: every absolute number in Chapter 4 (65.9 s, 342.4 s, 190 veh/min) is physically meaningless, and the demand of 18,000 veh/h is not a realistic load for a 12-lane intersection either.

Minimum fix: state a px→m and frame→s conversion, report the implied saturation flow, and add a sentence acknowledging it is not calibrated to HCM or field data. Report all results as *relative* differences.
Better fix: tune vehicle length, `movingGap`, and speeds so the implied saturation headway lands near 2 s, then re-run. Absolute delays then become quotable.

### 3.5 Arrivals are deterministic bursts, not a stochastic process

[core/generator.py:81-82](../core/generator.py#L81-L82) spawns 5 vehicles instantly then sleeps 1 s. This is a perfectly regular burst process, not the Poisson arrivals standard in traffic simulation. Regular arrivals systematically *understate* queueing delay and eliminate the arrival randomness that adaptive control is specifically supposed to exploit.

Fix: exponential inter-arrival times (`random.expovariate(rate)`). This is a five-line change with a large credibility payoff, and it may *strengthen* the adaptive result.

### 3.6 No conflict modelling, no spillback, unbounded storage

- Vehicles from different approaches pass through each other; turning vehicles cross opposing traffic with no conflict check. No collisions, no gap acceptance for permitted left turns.
- Queues grow off-screen indefinitely ([models/vehicle.py:96-102](../models/vehicle.py#L96-L102) stacks each new vehicle 100 px behind the last). There is no link storage limit and no spillback to upstream intersections. At v/c ≈ 1.8 the real failure mode of this intersection would be gridlock from spillback — which cannot occur here.

Both should be stated as limitations. Bounded storage would be a meaningful extension.

### 3.7 Thread-safety and timing

- The simulation is **wall-clock driven**, not discrete-event: controllers use `time.sleep(1)`, the renderer is capped at 60 FPS ([main.py:96](../main.py#L96)), and batches ran 5 concurrent instances. Under CPU pressure the frame rate drops but the signal timers do not, so *vehicle motion and signal timing can drift apart*. The cross-day agreement (±0.5 pp) is good evidence this did not bite, but it is a structural weakness that a reviewer can name for free.
  **Fix:** add a headless, fixed-timestep mode — decouple simulation steps from wall-clock, advance a virtual clock N steps per second, and let the controller count simulation ticks. This also makes runs reproducible and much faster than real time.
- `state.vehicles[dir][lane]` lists are mutated by the generator and render threads while [utils/counters.py:23](../utils/counters.py#L23) iterates them from the controller thread, with no lock. This is a live race condition; it can raise mid-iteration and is a plausible cause of the aborted runs that left 35 orphan signal logs. Guard the shared structures.

> **Note on the thesis text:** §3.3.1 (p. 29) states "a discrete time-step technique is used by the simulation, with vehicle states, traffic signals, and lane queues being updated every second." That is not what the code does. Vehicles update per rendered frame (~60 Hz, load-dependent); only signal countdowns are per-second. This sentence must be corrected.

---

## 4. Data collection — four defects that must be fixed

These are the specific items the faculty comment about "how we are collecting data" most likely points at.

### 4.1 Differential right-censoring — the most serious one

Only vehicles that **cross the stop line** are logged ([models/vehicle.py:398-399](../models/vehicle.py#L398-L399)). Everything still queued at run end is silently discarded. Under permanent oversaturation that is not a rounding error:

| Duration | Fixed: served / arrived | Priority: served / arrived | **Unlogged (fixed)** | **Unlogged (priority)** |
|---|---|---|---|---|
| 300 s | 787 / 1500 | 885 / 1500 | **47.5%** | **41.0%** |
| 600 s | 1638 / 3000 | 1861 / 3000 | **45.4%** | **38.0%** |
| 1200 s | 3317 / 6000 | 3805 / 6000 | **44.7%** | **36.6%** |
| 1800 s | 4933 / 9000 | 5723 / 9000 | **45.2%** | **36.4%** |

**Between 36% and 48% of all vehicles never appear in the data, and the censoring rate differs between the two arms by 6–9 percentage points.** The vehicles omitted are systematically the longest-waiting ones, and the fixed-time arm omits more of them. Mean and maximum delay are therefore biased downward for *both* arms and *more strongly for fixed-time*.

The direction of the bias is favourable to you — the true priority advantage in delay is larger than reported — but you must say so, because an unstated differential censoring of 40% invalidates the delay comparison outright, whereas a stated and quantified one is a strength.

**Three fixes, do all of them:**
1. **Log a run-end snapshot.** At `state.running = False`, write every still-queued vehicle with its accumulated wait and a `censored=1` flag. Costs nothing and lets you report a proper lower bound (assume each still-queued vehicle's wait ≥ its accumulated wait).
2. **Report the residual queue as a first-class metric.** "Vehicles remaining in queue at run end" is arguably a *better* oversaturation metric than mean delay, and it is currently thrown away. It is also not just a restatement of throughput plus arrivals if you break it down by approach.
3. **Add an equal-sample comparison.** Compare the delay of the first *N* vehicles served in each arm, where *N* = the smaller arm's count. You already have `analyzers/analyze_first_n_vehicles.py` for this — use it, and report it in the thesis.

### 4.2 `vehicle_id` is not an identifier

[utils/logger.py:54](../utils/logger.py#L54) writes `id(vehicle)` — a CPython memory address, reused after garbage collection. In the 1800 s fixed arm, 73,999 records collapse to 51,929 distinct "ids". Table 3.1 (p. 31) describes this field as "Unique identifier assigned to each vehicle." That is false as written, and `analyzers/analyze_log.py:126` reports a `unique_vehicles` column computed from it that is pure artefact.

**Fix:** monotonic counter assigned at construction (`itertools.count()`), logged alongside spawn timestamp, direction, lane, class, and turn intent. Never report `unique_vehicles` from the existing data.

### 4.3 No RNG seeding — runs are not reproducible

There is no `random.seed()` anywhere in the active code (verified by grep across `core/`, `models/`, `utils/`, `main.py`). Python auto-seeds from OS entropy, so runs *are* independent — but no seed is recorded, so **no run in this dataset can be reproduced**, and Section 3.4.2's claim that "each run used a fresh random seed" describes an intention rather than an implementation.

**Fix, and it is a double win:**
1. Seed explicitly per run (`--seed k`) and record the seed in the log filename and header. Reproducibility is a hard requirement at most venues.
2. Use **common random numbers**: run arm A and arm B on the *same* seed, so both controllers face a byte-identical arrival stream. Then compare *paired* differences. This is the standard variance-reduction technique for simulation experiments, it makes the comparison far tighter, and it lets you use a paired *t*-test / Wilcoxon instead of unpaired Welch. With your CV already at 0.3–0.9%, pairing would let you cut replications substantially or detect much smaller effects.

### 4.4 Logging I/O is inside the hot loop

`log_vehicle` opens, writes, and closes the CSV for **every single crossing** ([utils/logger.py:61-63](../utils/logger.py#L61-L63)), as does `log_signal_change`. At ~190 veh/min × 5 concurrent instances that is a continuous stream of open/close syscalls on the same wall-clock-timed process. It is almost certainly also the cause of the four null-padded, truncated signal logs in `even/1800`.

**Fix:** open once, keep the handle, buffer, flush periodically, close on exit. Also record run metadata (seed, mode, duration, git commit, host) in a header or sidecar JSON so runs are self-describing.

### 4.5 Undocumented data attrition

The dataset contains 4 corrupted signal logs and 45 orphan signal logs with no matching vehicle log (aborted runs). These are currently excluded from analysis silently. Any exclusion applied to a dataset must be reported: state how many runs were started, how many completed, how many were excluded and why. Unreported attrition is a standard reviewer objection.

---

## 5. Algorithm — the gaps that are "still questionable"

### 5.1 The `0.75` constant is not what the thesis says it is

Chapter 3 (pp. 33–34) justifies `0.75` as "the time it takes for one vehicle to pass the intersection". Two problems:

1. **It is not applied to a vehicle count.** It multiplies the *speed-weighted* count. The weights are `1/speed` ([utils/counters.py:26](../utils/counters.py#L26)) = {truck 0.667, bus 0.571, car 0.500, bike 0.444}, mean 0.5455. So effective allocation is `0.75 × 0.5455 × N ≈ 0.41 s per raw vehicle`, not 0.75 s.
2. **It ignores that three lanes discharge in parallel.** From §3.4 the simulated per-lane headway is 0.78 s, so clearing *N* vehicles from an approach needs `N/3 × 0.78 ≈ 0.26 s per vehicle`. The controller allocates ~1.6× more green than needed.

Ironically the *correct* formula is sitting commented out at [core/cycle_priority.py:58](../core/cycle_priority.py#L58): `(vehicle_count / lanes) * avg_headway + startup_loss`. That is the textbook form and it is defensible in a paper. The live formula is not.

**Fix:** either use the commented-out form with a measured headway, or keep `0.75` and justify it empirically ("calibrated by sweep; see sensitivity analysis"). Do not keep the current mismatch between the text's justification and the code's behaviour.

### 5.2 Two weighting schemes, one of them dead code

[utils/counters.py:5-10](../utils/counters.py#L5-L10) defines a PCU-style table `VEHICLE_WEIGHTS = {car: 1.0, bike: 0.5, truck: 2.0, bus: 2.5}` that is **never called**. The live weighting is `1/speed`, which is much flatter (a truck counts 1.5× a bike, not 4×).

`1/speed` is actually defensible — it is proportional to time-to-traverse — but it must be *named and justified as such*, not left as an undocumented accident sitting next to an unused table that implies a different method. Delete the dead table or wire it up and re-run. Do not describe PCU weighting in the thesis.

### 5.3 The "queue" the controller sees is physically impossible

`get_weighted_vehicle_counts()` counts **every uncrossed vehicle on the approach**, including vehicles spawned far off-screen. Under saturation that is a backlog of hundreds of vehicles stretching arbitrarily far upstream.

This is the direct mechanical cause of the cap saturation in §1.2 — the input to the green formula is unbounded, so the formula always saturates. It also undercuts the VANET framing: no RSU/AP deployment senses an unbounded queue. Real detection is a bounded zone (a few hundred metres, or the link length).

**Fix, and it is the highest-value algorithmic change in this list:** restrict counting to a detection zone of fixed length upstream of the stop line. This (a) makes the sensing model physically meaningful and consistent with Figure 3.1's architecture, (b) bounds the queue input so the green formula stops saturating, and (c) means the adaptive mechanism will actually engage. It may well shrink your headline number — but it converts an inactive mechanism into an active one, which is the whole point of the paper.

### 5.4 The starvation bound is a real result and is not stated

Because approaches are `pop`ped from the round-robin envelope ([core/cycle_priority.py:49](../core/cycle_priority.py#L49)), every approach is served **exactly once per round**. An approach therefore waits at most two rounds (~7 phases) between greens. This is a *provable* property, not an empirical observation, and it is exactly the answer to the standard objection against priority schemes ("won't a low-demand approach starve?").

State it as a short proposition with a one-line proof, and give the measured service-gap distribution as empirical confirmation: mean 115.1 s, max **204 s** (priority, 1800 s) versus a tightly bounded 68–69 s under fixed-time. Report the cost honestly — the guarantee is 3× looser than the baseline's — then note that it is bounded, which is more than most priority schemes offer.

### 5.5 The early-termination rule is dead code in this regime

`vc <= 3 and t >= 6` never fires under saturation. It is described in the thesis as an active mechanism. Either test it in a regime where it matters (undersaturated demand — see §6.2) or describe it accurately as inactive under the tested load.

### 5.6 The fairness variant is unevaluated

[core/cycle_fairness_priority.py](../core/cycle_fairness_priority.py) is implemented and selectable but has **no retained data**. Either run it as a third arm (cheap — it is one config change) or present it explicitly as an implemented-but-unevaluated extension. Do not let it appear in the thesis as though it were evaluated.

### 5.7 Untuned constants generally

`0.75`, the 24 s cap, the 6 s floor, the ≤3-vehicle early-exit threshold, and the 5 s yellow were never swept. Given that §1.2 shows *the cap determines the entire result*, a sensitivity analysis on the cap is not optional — it is the experiment that explains your own finding. Sweep 12/18/24/30 s and no-cap; the resulting curve is a figure in its own right and directly answers "where does adaptivity start to matter?"

---

## 6. Experimental design — what is missing

### 6.1 The matched-cycle baseline (do this first)

Everything in §1 reduces to one missing control. You compared a 68 s cycle against a 114 s cycle and attributed the difference to adaptivity.

**Add a third arm: fixed-time with 24 s green** (cycle = 4 × 29 = 116 s), matching the priority controller's realised cycle. Then:

- If priority still wins → the adaptivity claim is **established**, cleanly, and you can say so with confidence.
- If it does not → the honest finding is "the conventional baseline was under-timed; at matched cycle length, queue-responsive control's benefit under symmetric saturated demand is confined to equity, not throughput." **That is a more interesting and more publishable result than an unexamined win**, because it is a negative result that explains a widely-assumed positive one.

Cost: change `defaultGreen` in [config.py:2](../config.py#L2) to `{0:24, 1:24, 2:24, 3:24}`, add a mode label, run 150/80/30/15. A few hours of compute. There is no defensible reason not to run it.

### 6.2 Only one demand regime, and it is the wrong one for your thesis

All retained data is `uneven_mode = 'even'` at v/c ≈ 1.6–1.8. Two problems:

**Symmetric demand is the case where adaptive control has the least to offer.** With 25% of arrivals on each approach, there is nothing to reallocate. The generator already supports eight biased modes ([core/generator.py:25-59](../core/generator.py#L25-L59)) and **none of them was used in the retained dataset.** Running `up` (85/5/5/5) and `left_right` (35/15/35/15) tests exactly the mechanism the design targets, and should produce a much larger and much more defensible gain. This is the single best way to make "the difference between our approach and the regular approach more differentiable", which is what the faculty asked for.

**Permanent oversaturation is not where signals operate.** At v/c ≈ 1.8, queues never clear, no steady state exists, and delay is a function of run length rather than a property of the controller. Add 1.0–2.5 veh/s runs (v/c ≈ 0.4–0.9). Note the trade-off honestly: in the undersaturated regime the early-termination and demand-proportional mechanisms finally engage, but the *throughput* metric becomes uninformative (both controllers serve everything) and delay becomes the correct primary metric. That regime shift is itself worth a paragraph.

### 6.3 Suggested experiment matrix

| Arm | Demand mode | Rate (veh/s) | Runs × duration | Answers |
|---|---|---|---|---|
| fixed-12 (existing) | even | 5.0 | have it | baseline |
| priority (existing) | even | 5.0 | have it | current claim |
| **fixed-24 (new)** | even | 5.0 | 30 × 600 s | **the confound** |
| fixed-12 / fixed-24 / priority | `up` | 5.0 | 30 × 600 s each | asymmetric demand |
| fixed-12 / fixed-24 / priority | `left_right` | 5.0 | 30 × 600 s each | asymmetric demand |
| fixed-12 / fixed-24 / priority | even | 1.5 | 30 × 600 s each | undersaturated |
| fixed-12 / fixed-24 / priority | even | 2.5 | 30 × 600 s each | near capacity |
| priority, cap ∈ {12,18,24,30,∞} | even | 5.0 | 20 × 600 s each | cap sensitivity |
| fairness_priority | even + `up` | 5.0 | 30 × 600 s each | the unevaluated variant |

At 600 s per run with 5 concurrent instances this is roughly 20–25 hours of wall-clock compute — one weekend. With a headless fixed-timestep mode (§3.7) it would be a small fraction of that.

**On replication counts:** you do not need 150 runs. Your throughput CV is 0.3–0.9%; 20–30 paired runs with common random numbers detects a 1% difference comfortably. Spend the saved compute on *more conditions* instead of more replicates of one condition. Breadth is what this study lacks, not sample size.

---

## 7. Analysis and statistics — what to change

### 7.1 Report uncertainty

Chapter 4 reports point estimates only. Every number needs a confidence interval. From the existing data (95% CI on the mean over runs):

| Duration | Fixed throughput | Priority throughput | Fixed delay (s) | Priority delay (s) |
|---|---|---|---|---|
| 300 s | 787.2 ± 1.2 | 884.8 ± 1.2 | 65.91 ± 0.20 | 58.33 ± 0.17 |
| 600 s | 1638.0 ± 2.4 | 1860.7 ± 2.3 | 122.55 ± 0.34 | 102.65 ± 0.27 |
| 1200 s | 3316.6 ± 5.0 | 3804.5 ± 5.1 | 233.89 ± 0.55 | 189.80 ± 0.59 |
| 1800 s | 4933.3 ± 11.7 | 5723.3 ± 8.7 | 342.44 ± 0.85 | 276.17 ± 0.93 |

The intervals are tiny and non-overlapping. Showing that is far more convincing than a bare mean, and it costs you one column.

### 7.2 Significance testing is promised but not delivered

Methodology §3 step (6) states that "an analysis of the statistical significance is carried out for observed performance changes between systems." Chapter 4 contains no test, no *p*-value, and no effect size. Either do it or remove the claim.

When you do it, do it right: with cheap simulation replicates, significance is guaranteed and therefore uninformative (Welch's *t* on your data gives |t| ≈ 57–108). **Say that once and move to effect sizes** (Cohen's *d* ≈ 5–7 here, which is enormous by any standard) and confidence intervals on the *difference*. A reviewer who sees p < 0.001 offered as the headline evidence in a simulation study will mark you down; a reviewer who sees you explain *why* p-values are uninformative here will mark you up.

### 7.3 Maximum wait time is the wrong statistic, computed two different ways

Figure 4.2 reports max-over-all-runs (173 → 172 s at 5 min, −0.7%). The maximum of ~150 runs is an extreme order statistic — it estimates nothing stable and is dominated by whichever run happened to have the unluckiest vehicle.

Worse, the abstract reports "lowered maximum waiting time by 5.1%", which is the *mean of per-run maxima* (152.1 → 144.3), a different estimator from the one in Figure 4.2. **Two different numbers for the same named metric appear in the same document.** Fix this before anything else in Chapter 4 — it is the kind of inconsistency that makes a reviewer distrust the rest.

**Replace with percentiles**, which are stable and informative:

| Duration | p90 fixed → priority | p95 fixed → priority | mean-of-max fixed → priority |
|---|---|---|---|
| 300 s | 112.2 → 99.6 s (−11.3%) | 120.7 → 111.8 s (−7.4%) | 152.1 → 144.3 s (−5.1%) |
| 600 s | 214.4 → 179.8 s (−16.1%) | 229.2 → 193.4 s (−15.6%) | 277.9 → 245.1 s (−11.8%) |
| 1200 s | 409.7 → 329.6 s (−19.6%) | 439.4 → 358.4 s (−18.4%) | 521.4 → 442.9 s (−15.0%) |
| 1800 s | 614.9 → 485.9 s (−21.0%) | 657.2 → 521.7 s (−20.6%) | 783.3 → 632.1 s (−19.3%) |

This supports a genuinely useful claim the thesis currently cannot make: **priority improves the tail as well as the mean — it is not trading worst-case delay for average delay.** That is the standard objection to priority schemes, and you can answer it with data you already have.

### 7.4 Report the equity result — this is your best finding

Chapter 4's introduction names Fairness as one of four evaluation metrics. It then receives no section, no table, no figure, and one qualitative sentence in the Discussion. Meanwhile the existing data contain this:

| Duration | Algo | right | down | left | up | **Spread** | SD | Jain |
|---|---|---|---|---|---|---|---|---|
| 300 s | fixed | 66.9 | 55.9 | 63.7 | 76.9 | **21.1 s** | 7.55 | 0.9870 |
| 300 s | priority | 57.6 | 58.4 | 58.2 | 58.6 | **1.0 s** | 0.36 | 1.0000 |
| 1800 s | fixed | 344.5 | 327.9 | 344.7 | 352.6 | **24.6 s** | 8.98 | 0.9993 |
| 1800 s | priority | 274.9 | 274.7 | 276.9 | 277.9 | **3.2 s** | 1.33 | 1.0000 |

The priority controller is **3× to 21× more even across approaches**, and the finding is counter-intuitive in a way that makes it memorable: *a controller that deliberately prioritises one approach produces more equal outcomes than one that treats all approaches identically.* The explanation is clean — fixed-time is fair in **input** (equal green) but not in **output**; random arrival imbalance persists because open-loop control has no mechanism to correct it, while the priority controller closes the loop and equalises *queues* rather than *green time*.

Crucially, this is the **one result in the dataset that is not explained by cycle length.** The ordering mechanism is genuinely active — only 26.6% of priority phase transitions follow the round-robin successor, versus 100% for fixed-time — and ordering is what produces equity. So the corrected story is:

> **Throughput gain → cycle length. Equity gain → adaptive ordering.**

That is a clean, mechanistic, defensible two-part claim, and both halves are supported by data you already have.

### 7.5 Add metrics that are not restatements of throughput

Given §1.3, add measures that carry independent information:

- **Residual queue at run end**, total and per approach (currently discarded — see §4.1).
- **Per-approach green share vs. demand share** — the direct measure of "did allocation follow demand?"
- **Fraction of green time spent with an empty approach** ("wasted green") — the mechanism the paper claims to eliminate, currently never measured.
- **Service-gap distribution** (§5.4) — the cost of the policy.
- **Delay by vehicle class**, to confirm the controller does not systematically disadvantage slow vehicles. (It does not: under both controllers the ordering is bike > car > bus > truck, a car-following artefact, with priority uniformly lower.)

### 7.6 Fix the figures

- Figure 4.4 stacks three curves that are the same quantity (§1.3); it reads as triple confirmation. Replace with a single throughput panel plus an equity panel.
- Figure 4.2 is missing from the List of Figures.
- Section numbering jumps from 4.3 to 4.7.
- Figure 4.1 has a Windows activation watermark visible in the bottom-right corner. Regenerate it.
- Several figures duplicate what a table already says. Prefer one good figure per claim.

---

## 8. Factual corrections needed in the current report

These are internal inconsistencies and code-contradicting statements. Each is individually small; collectively they cost credibility.

| Location | Says | Should say |
|---|---|---|
| p. 33, p. 35 | Yellow phase is **4 seconds** | Code uses `defaultYellow = 5` ([config.py:4](../config.py#L4)). It is **5 s**. |
| p. 34 | "Vehicles were generated at a rate of **one vehicle per second**" | Contradicts Table 3.1 and Table 3.2 (5 veh/s) and the code. It is **5 veh/s**. |
| Table 3.2 | "Total simulation runs: **300**" | 275 per algorithm, **550 total**. |
| Table 3.1 | Vehicle id = "Unique identifier assigned to each vehicle" | It is `id(vehicle)`, a reused memory address (§4.2). |
| p. 29 (§3.3.1) | "a discrete time-step technique is used… updated every second" | Wall-clock real-time; vehicles update per frame (§3.7). |
| p. 30 (§3.3.2) | "First-In-First-Out (FIFO) queue management" ensures fair operation | There is no FIFO queue structure; ordering is emergent from per-lane car-following. |
| p. 29 (§3.3.2) | "four entering and four exiting approaches" with turning described | Turning *is* implemented — but the report never describes the turn model, turn probability (0.5), or that 33.3% of vehicles turn. This is real work that is going unclaimed. |
| Abstract | "lowered maximum waiting time by 5.1%" | Inconsistent with Figure 4.2's −0.7% (§7.3). Pick one estimator. |
| Abstract | Mixes 11.5% delay, 12.4% throughput (both 5-min) with 5.1% max | State the duration for every number, or report the range across durations. |
| §3.4.1 | Describes early termination and demand-proportional green as active mechanisms | Both are effectively inactive under the tested load (§1.2, §5.5). |
| Ch. 4 intro | Names Fairness as one of four metrics | Never reported (§7.4). |
| Throughout | "vehicle count" in the green formula | It is a *speed-weighted* count (§5.1). |

---

## 9. Positioning, literature, and venue

### 9.1 The VANET framing is currently decorative

Chapter 1 and §3.2 build an elaborate OBU/AP/RSU/TSC architecture (Figure 3.1). The simulation implements **none of it**: queue counts are read directly out of simulator memory ([utils/counters.py](../utils/counters.py)) with perfect accuracy, zero latency, unlimited range, and no packet loss. The word "VANET" in the title is doing work the experiment does not support.

Two honest options:

- **Narrow the claim.** Retitle around adaptive signal control, and present the VANET architecture as the assumed sensing substrate with perfect sensing stated as an explicit assumption. Cheapest, and entirely defensible.
- **Make it real.** Add a sensing layer with (a) a bounded detection zone (§5.3), (b) beacon interval / update latency, (c) packet loss probability, (d) partial penetration rate (only *p*% of vehicles have OBUs). **Penetration rate is the most valuable of these** — "how much of the benefit survives at 20% OBU penetration?" is a genuinely publishable question, it is directly relevant to real deployment, and it makes the VANET framing load-bearing. This is the most promising path to a novel contribution beyond the current comparison.

### 9.2 The literature review is too thin

Three papers reviewed in detail, seven references total. For a journal or conference submission this is far short. You need, at minimum:

- **Classical adaptive control** — SCOOT, SCATS, and especially **max-pressure control** (Varaiya 2013 and successors). Max-pressure is the closest well-known relative of your algorithm and has provable throughput-optimality; a reviewer *will* ask how your method relates to it. Not citing it looks like not knowing about it.
- **Webster's optimal cycle length formula.** This is directly relevant: Webster predicts that the optimal cycle grows with degree of saturation and lost time, which independently explains why your longer cycle wins. Citing it turns your §1.1 finding from an embarrassment into a *confirmation of established theory* — a far better position.
- **Actuated control** (gap-out/max-out), which is what your early-termination rule reinvents.
- **RL-based signal control**, which is the current mainstream of this literature and which you should position against (your simplicity/interpretability argument is a real advantage — make it explicitly).
- **HCM 2010/2016** for delay definitions, saturation flow, and lost-time conventions.

### 9.3 Realistic venue

As it stands: a departmental thesis, defensible with the corrections in §8.

With items 1–4 of §2 done: a solid conference paper at an ITS/VANET/smart-cities venue, or a mid-tier journal. The distinguishing asset is not the algorithm — it is the **replication scale and the mechanistic decomposition**. Very few papers in this space run 550 replications and then explain *which component of their method produced the gain*. Lead with that.

The most publishable framing is:

> *"A high-replication empirical decomposition of where adaptive-signal gains actually come from — showing that under saturated symmetric demand the throughput benefit attributed to demand-responsive allocation is almost entirely a cycle-length effect, while the equity benefit is genuinely attributable to adaptive phase ordering."*

That is a contribution. "Our method is 16% better" is not — everyone's method is 16% better.

---

## 10. Rewritten claims

### 10.1 Claims to retire

- ❌ "The proposed algorithm outperforms fixed-time on every evaluated statistic." (The statistics are not independent — §1.3.)
- ❌ "This adaptive behavior significantly improves intersection throughput and minimizes average wait time." (Not shown to be the adaptivity — §1.1.)
- ❌ "The improvements are attributed to the queue-based decision-making mechanism." (True for equity; false for throughput.)
- ❌ Any absolute delay figure presented as physically meaningful (uncalibrated model — §3.4).
- ❌ Any claim that the early-termination or demand-proportional mechanism is active under the tested load.

### 10.2 Claims you can defend today, from existing data

- ✅ Under saturated symmetric demand, the priority controller discharges **12.4–16.0% more vehicles** than a 12 s-green fixed-time baseline, with the advantage growing with run length. (n = 15–150/arm, CV < 1%, replicated across three collection days to within 0.5 pp.)
- ✅ **The gain is mechanistically attributable to reduced lost time per hour**, not to demand-responsive allocation: both controllers discharge at an identical saturation flow of 3.8–3.9 veh/s, and throughput tracks total green time to within 1.4%.
- ✅ The demand-proportional rule is **inactive** in this regime: 71–95% of phases are pinned at the green cap.
- ✅ The adaptive **ordering** is fully active (only 26.6% of transitions follow the round-robin successor) and produces a **3×–21× reduction in the spread of per-approach mean delay** (24.6 s → 3.2 s at 1800 s; Jain 0.9993 → 1.0000).
- ✅ Priority improves p90/p95/max delay as well as the mean — **no mean-versus-tail trade-off**.
- ✅ The cost is a weaker service guarantee: max interval between successive greens rises from a bounded 69 s to 204 s, with 10.2% of gaps exceeding 120 s — bounded by construction at two rounds.

### 10.3 Draft replacement abstract

> Fixed-time signal control allocates green independently of demand, wasting capacity at intersections with fluctuating arrivals. This work presents a high-replication microscopic simulation study comparing a conventional fixed-time controller against a queue-responsive priority controller at an isolated four-approach intersection with three lanes per approach and turning movements. The priority controller serves approaches in descending order of a speed-weighted queue count and allocates green proportional to that queue, bounded to [6 s, 24 s], while guaranteeing each approach exactly one service per round. Both controllers were evaluated over 550 runs (≈86 simulated hours, 904,170 logged crossings) at four run lengths under saturated, directionally uniform demand. The priority controller increased throughput by 12.4–16.0% and reduced mean stopped delay by 11.5–19.4%, with 90th-percentile and maximum delay improving by comparable margins, and the spread in per-approach mean delay falling from 24.6 s to 3.2 s over 30-minute runs. **A phase-level decomposition shows these two results have different causes.** Both controllers discharge traffic at an identical saturation flow, so the throughput gain is attributable almost entirely to a reduction in lost time from 29.4% to 17.6% of cycle length — under saturation the controller reached its green cap in 71–95% of phases, leaving demand-proportional allocation rarely binding. The equity improvement, by contrast, derives directly from adaptive phase ordering, which remains fully active. **We therefore report a matched-cycle fixed-time baseline** to separate the two effects [← after running §6.1]. The adaptive policy's cost is a weaker service guarantee, with the maximum interval between successive greens rising from 69 s to 204 s.

Note how much stronger this reads than the original. It says something specific, it pre-empts the reviewer's best objection by raising it first, and it reports a mechanism rather than a percentage.

---

## 11. Concrete code changes

Ordered as a single work session. None of these is large.

| # | File | Change |
|---|---|---|
| 1 | [utils/logger.py:54](../utils/logger.py#L54) | Replace `id(vehicle)` with a monotonic counter assigned in `Vehicle.__init__`. |
| 2 | [utils/logger.py:61](../utils/logger.py#L61) | Hold the file handle open; buffer and flush periodically instead of open/close per row. |
| 3 | `utils/logger.py` (new) | `log_residual_queue()` — on shutdown, write every still-queued vehicle with `censored=1`. |
| 4 | [core/generator.py](../core/generator.py) | Accept a `--seed`; call `random.seed(seed)`; record the seed in the filename and log header. |
| 5 | [core/generator.py:81](../core/generator.py#L81) | Replace the 5-per-burst loop with exponential inter-arrival times. |
| 6 | [state.py](../state.py) | Move `currentMode`, `uneven_mode`, `duration`, `seed`, `arrival_rate` to CLI arguments so a batch can mix arms and both arms can share a seed. |
| 7 | [utils/counters.py](../utils/counters.py) | Add a `DETECTION_ZONE_PX` limit; count only vehicles within it. Delete or wire up `VEHICLE_WEIGHTS`. |
| 8 | [utils/counters.py](../utils/counters.py) / [models/vehicle.py](../models/vehicle.py) | Guard shared lane lists with a lock, or snapshot under lock before iterating. |
| 9 | [config.py:2](../config.py#L2) | Parameterise `defaultGreen` so the fixed-24 arm is a flag, not an edit. |
| 10 | [core/cycle_priority.py:60](../core/cycle_priority.py#L60) | Make `0.75` and the `[6, 24]` bounds configurable for the sensitivity sweep. |
| 11 | [main.py](../main.py) | Add `--headless` and a fixed-timestep mode: advance a virtual clock, decouple from wall-clock and from rendering. Controllers count ticks, not `time.sleep`. |
| 12 | Both controllers | Add a 1–2 s all-red clearance; allow vehicles within *X* px of the stop line to clear on yellow. |
| 13 | [models/vehicle.py](../models/vehicle.py) | Add startup lost time / simple acceleration ramp. |
| 14 | `analyzers/` (new) | One analyzer producing the full results table with 95% CIs, percentiles, Jain's index, residual queue, green share vs demand share, and service-gap distribution — one script, one CSV, so the thesis tables are regenerable. |
| 15 | [analyzers/analyze_log.py:126](../analyzers/analyze_log.py#L126) | Remove the `unique_vehicles` column, or fix it once change #1 lands. |

Item 11 is the highest-leverage: a headless fixed-timestep mode makes runs reproducible, removes the CPU-load confound, and lets the entire experiment matrix in §6.3 run in a fraction of the wall-clock time.

---

## 12. Suggested sequence

**Week 1 — credibility.** Code changes 1–10 and 15. Fix every item in §8. Write the equity section (§7.4) and the percentile table (§7.3) from existing data. *No new runs needed; the thesis is already meaningfully better.*

**Week 2 — the missing control.** Run the fixed-24 arm (§6.1). Write §1's decomposition into the Discussion regardless of which way it comes out. *This is the item that decides whether the paper is publishable.*

**Week 3 — breadth.** Asymmetric demand and undersaturated demand (§6.2), plus the cap sensitivity sweep. *This is where the "our approach is clearly different from the regular approach" evidence actually comes from.*

**Week 4 — model quality, if time allows.** Fixed-timestep headless mode, startup lost time, yellow usage, calibrated headway. Re-run the core matrix. Add the literature in §9.2 and rewrite the abstract and conclusion.

If only one week is available, do Week 1 plus the single fixed-24 experiment. That combination converts the central weakness into the central contribution, which is the whole game.

---

## Appendix A — Verification commands

Every number in this document is reproducible from the repository:

```bash
# Per-run throughput and delay, with 95% CIs and first/second-half split
python3 -c "$(cat <<'PY'
import csv,glob,statistics as st
for dur in ["300","600","1200","1800"]:
    for mode in ["fixed","priority"]:
        thr=[];mean=[]
        for p in sorted(glob.glob(f"data/logs/even/{dur}/{mode}_*.csv")):
            w=[float(r['wait_time_sec']) for r in csv.DictReader(open(p)) if r.get('wait_time_sec')]
            if w: thr.append(len(w)); mean.append(sum(w)/len(w))
        m,s=st.mean(thr),st.stdev(thr); d=st.mean(mean)
        print(f"{mode:9s}{dur:>5s}s n={len(thr):3d} thr={m:8.1f}±{1.96*s/len(thr)**.5:4.1f} delay={d:7.2f} served={100*m/(5*int(dur)):.1f}%")
PY
)"
```

Signal-phase analysis (cap saturation, cycle length, service gaps) is in the same form over `data/log_signals/even/<dur>/*_signal.csv`, differencing consecutive green-onset timestamps.

## Appendix B — Reviewer questions to be ready for

1. *"Your adaptive controller is at its cap 95% of the time. How is this adaptive?"* → §1.2, §6.1. **Must have the fixed-24 arm to answer.**
2. *"Isn't your delay result just your throughput result?"* → §1.3. Answer with the deterministic-queueing derivation and pivot to equity.
3. *"Why is the baseline serving one approach at a time?"* → §3.1. Either fix it or scope it explicitly.
4. *"What is your saturation flow rate?"* → 4,600 veh/h/lane, ~2.4× field values. §3.4. State it.
5. *"How does this relate to max-pressure control?"* → §9.2. **Must cite it.**
6. *"You discarded 40% of your vehicles. How do you know the delay comparison holds?"* → §4.1. Answer with the censored-run-end snapshot and the equal-*N* comparison.
7. *"Where is the VANET? Your controller reads simulator memory."* → §9.1. Narrow the claim or add a sensing layer.
8. *"Are your results reproducible?"* → §4.3. **Currently: no.** Fix before submission.
