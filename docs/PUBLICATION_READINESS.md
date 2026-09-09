# Publication readiness — start here next session

**Reviewed: 10 September 2026.** Basis: current source, README, all five existing Markdown documents, the [current thesis PDF](Thesis_Report_5-9-26_update.pdf), and the pasted progress review. Historical code was checked for context. `data/` was excluded; historical numbers below are documented findings, not newly verified results.

**Verdict:** the project has moved from a demonstration toward a controlled experiment. The core controller and paired-replay infrastructure exist. It is **not yet ready for definitive result collection or a conference submission**: measurement integrity, model credibility, and the experimental design still need work. This is several substantive work stages away, not just a plotting exercise; a reliable calendar estimate needs the first validation runs.

## The method we are preserving

Serve each of the four **approaches** once per round. Select the largest queue, serve it, remove it from that round, then recount and reorder only the remaining approaches. Start a new round after all four are served.

The [implementation](../core/cycle_priority.py) uses `W = sum(1 / configured_vehicle_speed)` across all uncrossed vehicles in an approach's three lanes, including moving/off-screen vehicles. Green is `max(6, min(int(0.75 * W), 24))` seconds, calculated once at green onset. It stays fixed during that green. This is a weighted count, not physical queue length or continuously adjusted green. Preserve this behavior and describe it precisely; resolve any intended difference before experiments.

## Already done

- [x] Modular simulation, turning movements, following behavior, and removal of departed vehicles implemented. These are engineering improvements, not traffic-model validation.
- [x] Fixed baseline retimed from 12 to **24 seconds**; yellow currently **5 seconds** for both controllers.
- [x] Variable total demand (0.5/2/4 vehicles per second, switching every 120 seconds) and static directional skews implemented. Inter-arrival times remain regular within each load period.
- [x] Vehicle-count termination, timeout metadata, and separate output locations for time, count, and paired runs implemented.
- [x] Seeded plans, shared sampling, prescribed arrivals/turns, `plan_seq`, sequential controller runs, FPS/drift recording, and paired summaries implemented.
- [x] Sampler equivalence rechecked here: all 36 mode/seed combinations passed, 1,000 draws each. Same-seed N=500 plan hashes also matched. Earlier end-to-end checks are documented in [PAIRED_REPLAY_PLAN.md](PAIRED_REPLAY_PLAN.md); they were not rerun here.

**Evidence so far:** the [historical review](THESIS_IMPROVEMENT_PLAN.md) shows that longer greens and reduced yellow-time overhead explain most of the old throughput advantage. It does not isolate an ordering benefit. The [variable-load pilot](VARIABLE_LOAD_PILOT_2026-08-25.md) suggests lower stopped delay, but its arrivals were unpaired; grouping by realized crossings does not control offered demand. Neither that pilot nor the documented N=12 replay establishes a general efficiency gain. Full-scale paired evidence remains undocumented.

## Remaining checklist, in order

### 1. Make measurements trustworthy

- [x] **Repair the paired validity gate** in [analyze_paired.py](../analyzers/analyze_paired.py). It now requires a verified plan hash, complete run identity/counts/timing, matching startup configuration/source fingerprints, exactly one crossing per expected `plan_seq`, matching type/direction/lane/turn attributes, and finite nonnegative waits. Invalid pairs produce rejection reasons and no effect estimates. Startup fingerprints include configuration, timeout, simulation source and image assets. The driver archives external plans and refuses existing arm folders. Core scheduling and green calculation are unchanged.
- [x] **Unify timing and verify replay at scale.** One monotonic run clock now serves main, the generator and the controllers, so releases, greens and crossings share an origin. Releases, crossings, per-phase decisions and the whole FPS window series are recorded; the last crossing is reported apart from the display drain. Verified at N=500 on this machine — see the measurements below. Physics still runs inside the renderer at a 60 FPS cap rather than on fixed physics steps; that remains the standing risk. Two open items carry forward: measure a second machine before tightening the provisional 250 ms / 5% limits, and move to fixed physics steps if a slower machine changes outcomes, preserving the controller's decisions.
- [ ] **Validate the traffic model and observation boundary.** Discharge headways, startup delay, green utilisation and entry-to-stop-line travel time are now measured (see below) and the first two are clearly unrealistic; calibration has not been attempted yet. Still to check: turning/merge conflicts, turning/merge conflicts, clearance, directional geometry, and conservation of vehicles. Spawn distance currently depends on the preceding queue, so identical planned arrivals can start at different positions across controllers; measure entry-to-stop-line elapsed time alongside stopped delay. State spatial/time units and justify single-approach phasing, unlimited storage, and perfect sensing. Calibrate against suitable measurements or cross-check key findings in an established simulator before claiming realistic traffic efficiency. [FHWA guidance](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm) distinguishes a working model from a calibrated one.

### 2. Freeze an experiment that can find wins and losses

- [x] **Predefine scenarios and reserve fresh evaluation seeds.** Cross balanced, moderately skewed, and strongly skewed demand with below-capacity, near-capacity, and overloaded conditions, assessed per approach. Include changing demand and recovery. Changing which approach is busiest needs a plan extension; current skews stay fixed. Hypothesis: uneven/changing demand with greens away from both bounds may benefit; persistent overload may erase that benefit. Include neutral and adverse cases, and verify actual green-duration distributions rather than selecting only favorable runs.

  **Status:** frozen in [`scripts/scenarios.py`](../scripts/scenarios.py) and written up in [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md) — three skews crossed with four regimes, development seeds 301–308, evaluation seeds 9001–9020 held back. Plans can pin one demand regime, and pinning changes arrival times only, not the vehicle draws. Green-duration distributions are recorded per arm. Still open: which approach is busiest cannot change mid-run, so "changing demand" means changing *total* demand only.
- [ ] **Use competitive controls and isolate the mechanism.** Keep fixed-24 as a diagnostic, but also tune fixed timing/splits on separate development plans and include a simple actuated comparator. Add experimental arms for fixed order with adaptive duration and adaptive order with constant duration. These isolate ordering and timing without changing the proposed controller. `fairness_priority` changes several rules together and is not a clean ablation. Keep phasing/clearance consistent across arms.

  **Status:** half done. `fixed_order_adaptive_duration` and `adaptive_order_fixed_duration` exist as arms and run, and the dispatch no longer falls back to fixed on an unknown controller name. Still missing, and both are needed before any novelty claim: a fixed plan with tuned splits, and an actuated comparator.
- [x] **Define the workload and inference before collection.** Choose N/horizon to cover several load transitions; specify initialization, arrival cutoff, draining, and timeout handling. Analyze finite-workload clearance separately from sustained-flow performance. A time-limited study needs residual-queue logging. Retain/report all failures by scenario and arm; do not hide difficult cases through exclusions. Use independent plan-level differences and 95% confidence intervals, stratified by scenario; choose replication count from pilot variability and desired precision. Vehicle-level p-values are unsuitable as the main evidence because vehicles interact; the batch analyzer already uses plan means. [Wilcoxon assumptions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html) still need checking.

  **Status:** written up in [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md). The analyzer reports plan-level bootstrap intervals stratified by scenario, counts invalid pairs per scenario, and sizes the next round from pilot variability. Wilcoxon is reported but is not the claim; its assumptions are still unchecked.

### 3. Generate a small, reproducible publication package

- [x] **Extend logging and analysis:** record decision-time counts, round/phase identity, selected and actual green duration, green end, queue traces, and actual arrival/crossing times. Current green-onset logs cannot fully reconstruct the final phase or explain every decision.

  **Status:** paired runs write a phase log carrying round/phase identity, decision-time weighted and raw counts, selected green, actual green end and phase end, plus per-vehicle release and crossing times on one shared run clock. Queue traces are per-phase snapshots, not continuous.
- [ ] **Produce two tables and three figures:** configuration/scenario table; results table with independent-plan counts, failures, absolute effects and confidence intervals; delay-effect plot across demand/skew; per-approach mean and tail-delay plot with service gaps; mechanism plot showing green-bound frequency, green utilization, and ablation effects. Report stopped delay as the primary endpoint, p95 delay and worst-served approach as safeguards, and clearance time separately. With fixed N, `N / completion_time` is a transformation of completion time, not independent corroboration or a capacity estimate.

  **Status:** deferred by decision until the results are frozen — matplotlib is not installed and no plotting code exists yet. The results package already emits the configuration and results tables as Markdown.
- [ ] **Archive and position the contribution:** preserve plans, full configuration/code revision, dependencies, raw logs, analysis and figure commands outside the currently ignored-only `data/*` workflow. Compare with relevant queue-based/actuated literature before claiming novelty. The useful contribution to aim for is a reproducible account of **when this simple scheduling rule helps, why, and at what fairness cost**. VANET communication is conceptual here; packet exchange, loss, and latency are not simulated.

  **Status:** the mechanical half is done — [`scripts/export_results.py`](../scripts/export_results.py) writes plans, raw logs, derived analyses, code revision and commands into `results/`, outside the ignored `data/*` tree, and refuses to run from a dirty tree. The positioning half is untouched: no literature comparison has been done.

## University report versus conference paper

Keep the university report as its own evidence/version track. Its current printed pp. 40–43 mix fixed-count methodology with time-limit termination; Chapter 4 still reports the old time-based experiments. It also states 4-second yellow, describes ordering inconsistently between §§3.2 and 3.4.1, and gives qualitative fairness claims in §4.4. Figures 4.1 and 4.4 show no uncertainty. Do not transplant those results into the new methodology or update old configuration values as though the old runs used them. Build the conference methods and results from the frozen, validated experiment above.

## Timing and model measurements — 10 September 2026

Instrumentation added this session: a shared monotonic run clock, per-vehicle
`released_sec`/`crossed_sec`, a per-phase decision log (round/phase identity,
decision-time weights and queues, selected green, actual green end), the full
FPS window series, and the last-crossing time separated from the 1.5 s display
drain. Three analyzers read them: `analyze_timing.py` (clock comparability),
`analyze_discharge.py` (traffic-model behaviour) and the extended
`analyze_paired.py` (plan-level intervals, tail delay, worst-served approach).

### Replay repeatability, N=500, three identical fixed arms

Plan `even_500_seed201`, one machine, SDL dummy display, all three arms valid.

| Quantity | Result |
| --- | --- |
| Δ stopped delay between repeats | −0.008 s and −0.013 s on a mean of 47.42 s |
| Clearance time | 248.095 / 248.060 / 248.051 s (spread 45 ms) |
| Release lateness, worst | 4.4–4.8 ms (tolerance 250 ms) |
| Release gap between arms, worst | ≤ 4.7 ms |
| Phase onset gap between arms, worst | ≤ 15.1 ms |
| Green overrun against granted time, worst | 11.9–17.3 ms |
| FPS mean / worst window | 62.22–62.23 / 61.97–61.99 |
| FPS window gap between arms, p95 | ≤ 0.66% (tolerance 5%) |

**Reading:** on this machine the replay noise floor for stopped delay is about
0.01 s, roughly 0.03% of the mean. An effect below ~0.05 s is not
distinguishable from run-to-run jitter. The 250 ms drift and 5% FPS limits are
two orders of magnitude looser than observed behaviour; they are still the
right shape of check, but they would not catch a moderate regression. Tighten
them once a second machine has been measured — a single machine cannot set a
portable threshold.

### Traffic-model behaviour, same runs

Measured on the saturated N=500 runs, identical to three decimals across all
three repeats.

| Quantity | Simulated | Typical real-world |
| --- | --- | --- |
| Per-lane saturation headway (median) | 0.82 s | ≈ 1.9 s |
| Per-lane discharge implied | ≈ 4,400 veh/h | ≈ 1,900 veh/h |
| Startup delay to first crossing | 0.08 s | ≈ 2 s of startup lost time |
| Per-approach discharge (3 lanes) | 2.52 veh/s | ≈ 1.6 veh/s |
| Green utilisation | 0.81 | — |
| Crossings outside any green | 17 of 500 (3.4%) | — |

### Why discharge is too fast — traced to two parameters

The headway is not emergent; it is arithmetic. A vehicle follows at a fixed
pixel distance, so its headway is `(length + movingGap) / (speed × FPS)`:

| Type | Length px | Speed px/s | Spacing px | Predicted headway | Time gap kept |
| --- | --- | --- | --- | --- | --- |
| car | 54 | 124.4 | 69 | 0.56 s | 0.12 s |
| bus | 76 | 108.9 | 91 | 0.84 s | 0.14 s |
| truck | 62 | 93.3 | 77 | 0.83 s | 0.16 s |
| bike | 38 | 140.0 | 53 | 0.38 s | 0.11 s |

Those predictions bracket what was measured (median 0.82 s, p05 0.53 s), so
the discharge rate is fully explained by geometry. Taking a car to be 4.5 m
long fixes the scale at **1 px ≈ 0.083 m**, which makes the car speed
**10.4 m/s ≈ 37 km/h** — entirely reasonable for an urban approach. The speed
is not the problem. Two other things are:

1. **The following gap is a fixed distance, not a time.** `movingGap = 15 px`
   is about **1.25 m**, a time gap of **0.12 s** at car speed. Real
   car-following keeps something near 1.5–2 s. This single parameter is what
   makes greens roughly twice as productive here as in reality. Reaching a
   1.9 s saturation headway at the current speed needs a spacing of about
   236 px (≈ 19.7 m), i.e. `movingGap ≈ 182 px` rather than 15.
2. **There is no acceleration.** A vehicle moves at full speed on the frame
   the signal turns green, and the queue's lead vehicle waits 10 px from the
   stop line, which is why startup delay measured 0.08 s. A real approach
   loses roughly 2 s per phase to start-up. Every green here is therefore
   worth about two seconds more than its nominal length.

Both push the same way: greens are cheaper than they should be. That is
exactly the direction that flatters a controller whose advantage comes from
allocating green.

**What fixing it would cost.** Raising `movingGap` to ~182 px stretches queues
by roughly 3.4×, which collides with the unlimited-storage assumption and
would need the spawn geometry re-examined. Adding acceleration changes the
vehicle model itself. Neither is a tuning tweak, and both would invalidate
every number collected so far, including the pilot above. This is a decision
to take deliberately before the real collection, not during it.

**Reading:** the intersection discharges roughly 2.3× faster per lane than a
real one and has almost no startup lost time. This is the single largest
threat to any efficiency claim: greens are cheaper here than in reality, which
systematically favours whichever controller grants more green. It does not
invalidate a *paired* comparison — both arms discharge alike — but it does
invalidate absolute throughput and delay figures, and it may change the sign
of an ordering effect near capacity. Calibrating headway and startup loss is
now the top model task, ahead of collecting results.

### First replicated controller result — balanced demand, N=500

Eight independent plans (development seeds 301–308), `fixed` against
`priority`, balanced demand, mixed load regime. All eight pairs passed the
validity gate. Archived at
[`results/pilot_even_500_2026_09_10`](../results/pilot_even_500_2026_09_10).

| Quantity | Result |
| --- | --- |
| Δ mean stopped delay | **−11.42 s**, 95% CI **[−15.09, −8.12]** |
| Plans favouring `priority` | 8 of 8 |
| SD of plan-level effects | 5.43 s |
| Δ median of plan means | −8.81 s |

**Reading:** the effect is real *within this model* — about a thousand times
the 0.01 s replay noise floor, consistent in sign across every plan, and the
interval excludes zero comfortably. Two things stop it being a headline
result. Delay is measured in a simulation that discharges vehicles about
2.3× too fast, so the *magnitude* is not transferable. And this is one cell of
the grid — balanced demand — which the recorded hypothesis expects to be among
the *weaker* cases.

**What the mean hides, and what the safeguards show.** On two of the eight
plans (`seed303`, `seed308`) fewer than half the vehicles improved — win rates
0.446 and 0.454, with median differences of +5.67 s and +0.78 s — while the
mean still improved by 6.9 s and 8.9 s. So the effect is *not* "every vehicle
waits less" and must not be described that way.

The pooled safeguards say what is happening instead:

| Endpoint | Δ (plan means) | 95% CI | Worse under `priority` |
| --- | --- | --- | --- |
| Mean stopped delay | −11.42 s | [−15.09, −8.12] | 0 of 8 |
| p95 stopped delay | −17.66 s | [−28.97, −7.73] | 0 of 8 |
| Worst-served approach | −19.79 s | [−23.57, −14.68] | 0 of 8 |
| Gap between best and worst approach | −12.30 s | [−20.08, −4.32] | 2 of 8 |
| Clearance time | −20.89 s | [−31.99, −9.29] | 1 of 8 |

The tail improves *more* than the mean, and the worst-served approach improves
most of all. The mechanism is a reallocation: lightly delayed vehicles give up
a little so heavily delayed ones gain a lot. That is a defensible result and a
more interesting one than a uniform speed-up — but it is a claim about
distribution, so it has to be reported with the tail figures beside the mean,
never by the mean alone.

### Ablation, and what it suggests

A four-arm smoke run (N=20, one plan, over-capacity) exercised the new
`fixed_order_adaptive_duration` and `adaptive_order_fixed_duration` arms. The
duration arm captured almost all of the benefit and the ordering arm almost
none. **This is not evidence yet** — twenty vehicles and three phases, with
every green pinned to the 6 s lower bound. It is recorded only because it
points at the question the historical review already raised: whether the
advantage is ordering or simply longer greens. The grid must answer it.

### Strong skew: a very large effect, and why it should not be the headline

One pair from the grid slice, `right_medium_500_seed401` — 85% of demand on a
single approach, near capacity, N=500, valid:

| | `fixed` | `priority` |
| --- | --- | --- |
| Mean stopped delay | 108.60 s | 26.64 s |
| p95 stopped delay | 235.42 s | 56.57 s |
| Clearance | 601.53 s | 362.88 s |
| Δ mean stopped delay | | **−81.96 s**, win rate 0.846 |

Seven times the balanced-demand effect. The green distributions say exactly
where it comes from:

- `fixed`: twenty phases, **every one 24 s**.
- `priority`: **nineteen phases at the 6 s floor**, four at the 24 s ceiling.

Under an 85/5/5/5 split, fixed-24 spends roughly seventy-two seconds of every
cycle serving three nearly empty approaches. The proposed controller spends
eighteen. Almost the whole gain is *not serving an empty approach for 24
seconds*.

**This is a finding about the baseline, not about queue ordering.** Any
actuated controller — anything that gaps out when no one is waiting — would
recover most of this, and so would `fixed_order_adaptive_duration`, which
keeps the fixed rotation and changes only the duration rule. Reporting
−81.96 s against fixed-24 as evidence for demand-ordered scheduling would be
overclaiming, and a reviewer would say so immediately.

It also reorders the remaining work: **the ablation arms and an actuated
comparator now matter more than further replication of fixed-versus-priority.**
Replicating a comparison against a baseline nobody would deploy adds precision
to the wrong number.

### Ablation under strong skew: the benefit is duration, not ordering

This is the result the whole design was built to obtain. Both development
seeds of the strong-skew, near-capacity cell, N=500, six arms each, all valid.
`abl_fixed` is the baseline every other arm is compared against; the `fixed`
row is an independent replicate of it and serves as the noise-floor control.

| Arm | Order | Green duration | Δ mean delay, seed 401 | seed 402 |
| --- | --- | --- | --- | --- |
| `fixed` (replicate) | fixed | 24 s | −0.005 s | −0.001 s |
| `abl_ord` | **demand-ordered** | 24 s | **+0.836 s** | **+0.747 s** |
| `abl_dur` | fixed | **demand-sized** | **−81.860 s** | **−77.805 s** |
| `abl_both` (= `priority`) | demand-ordered | demand-sized | −82.052 s | −78.069 s |

**Demand-sized greens account for 99.8% and 99.7% of the effect. Demand
ordering accounts for none of it, and is very slightly harmful** — its win
rates are 0.35 and 0.31, so reordering makes most vehicles marginally worse
while leaving the mean essentially unchanged.

The green distributions explain why. `abl_dur` chooses exactly the same greens
as `priority` (`{6 s: 19, 17 s: 1, 24 s: 4}`), and `abl_ord` chooses exactly
the same greens as `fixed` (`{24 s: 20}`). When every green is 24 s, changing
the *order* of four phases of equal length leaves the cycle the same length,
so every approach still waits a full cycle and nothing improves.

The replicate control is worth noting on its own: an independent `fixed` run
placed in the same folder reproduced the baseline to 0.005 s and 0.001 s, so
the ablation harness itself is not introducing the difference.

**What this means for the thesis.** The contribution as currently framed —
serving the largest queue first — is not what produces the measured benefit.
What produces it is sizing green to demand, which is the older and much more
widely known idea. The honest framings available are:

- report the ordering rule as **not** beneficial in these scenarios, which is
  a real and publishable negative result, and make the duration rule the
  subject; or
- find the conditions, if any, under which ordering *does* pay — the
  balanced and changing-demand cells are the remaining candidates, and are
  running now.

Either way, the earlier [historical review](THESIS_IMPROVEMENT_PLAN.md)
suspicion is now confirmed by direct experiment rather than inference.

### Grid slice: the effect depends strongly on the cell

Three cells, two development seeds each (401, 402), N=500, all six pairs
valid.

| Cell | Skew / regime | Δ mean stopped delay | Win rate | Clearance |
| --- | --- | --- | --- | --- |
| `right_medium` | strong / near capacity | −81.96, −78.07 s | 0.846, 0.842 | 602→363, 591→353 s |
| `right_high` | strong / overloaded | −92.02, −89.83 s | 0.840, 0.860 | 598→361, 496→313 s |
| `even_high` | balanced / overloaded | −9.12, −9.96 s | **0.392, 0.480** | 272→243, **225→240 s** |

Both seeds agree closely within every cell, so these differences are between
cells, not noise.

Three things follow.

1. **Skew dominates.** The effect under strong skew is eight to nine times the
   balanced effect. As the previous section argues, that is mostly fixed-24
   failing under skew rather than ordering succeeding.
2. **Under balanced overload most vehicles lose.** Win rates of 0.392 and
   0.480 mean the majority of vehicles wait *longer*, while the mean still
   improves by about 9.5 s. The entire gain is tail reallocation. The recorded
   hypothesis — that persistent overload would erase the benefit — is half
   confirmed: the mean benefit shrinks to about a ninth, and the typical
   vehicle is worse off.
3. **Clearance and delay can disagree.** On `even_high` seed 402, clearance got
   *worse* (225 → 240 s) while mean delay improved. They are different
   endpoints and must be reported separately, never as one "efficiency" claim.

### How many plans the real study needs

From the pilot SD of 5.43 s, per scenario cell:

| Target CI half-width | Plans per cell | Pairs over 12 cells | Approx. 2-arm runtime |
| --- | --- | --- | --- |
| ±1 s | 114 | 1,368 | ~365 h |
| ±2 s | 29 | 348 | ~93 h |
| ±3 s | 13 | 156 | ~42 h |
| ±5 s | 5 | 60 | ~16 h |

At an effect size near 11 s, ±3 s resolves sign and rough magnitude per cell;
±1 s is not affordable at N=500 on this machine. Four arms roughly double
these figures. This is a multi-day compute budget and should be planned as
one, or N reduced — but N is also what makes clearance meaningful, so reducing
it is not free.

## Implementation checkpoint — 10 September 2026

**First step completed.** `python3 -m unittest discover -s tests -v` passes 16 tests, including duplicate/missing IDs, malformed plans/metadata, attribute mismatches, nonfinite measurements, provenance changes, ordinary-log compatibility and driver preflight. Sampler equivalence still passes all 36 combinations. Two sequential real simulator processes completed an N=1 fixed/fixed smoke test using SDL's dummy display; their logs passed the gate with one matched vehicle. Temporary fixtures/smoke outputs were written under `/tmp`; historical `data/` was not inspected or modified. This is a logging check, **not** timing or model validation.

**Compatibility:** old paired logs lack required provenance/attributes and will now be rejected; keep them as historical evidence and generate fresh runs. Vehicle-level p-values are no longer emitted as inference; batch tests continue to use plan means. Independence across plans and the final statistical protocol still need validation.

**Next step:** instrument and define timing/model acceptance checks before the windowed N=500 fixed/fixed repeats, then fixed/priority. Record actual last-crossing time separately from display drain, phase durations, release times and FPS windows. Use fresh plan IDs and keep every failed run. The 5% average-FPS and 250 ms drift thresholds remain provisional; passing the current gate does not establish simulation fidelity. After timing/model validation, freeze the experimental protocol before collecting publication results.
