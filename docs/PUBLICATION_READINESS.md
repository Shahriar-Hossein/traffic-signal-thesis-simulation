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

- [ ] **Predefine scenarios and reserve fresh evaluation seeds.** Cross balanced, moderately skewed, and strongly skewed demand with below-capacity, near-capacity, and overloaded conditions, assessed per approach. Include changing demand and recovery. Changing which approach is busiest needs a plan extension; current skews stay fixed. Hypothesis: uneven/changing demand with greens away from both bounds may benefit; persistent overload may erase that benefit. Include neutral and adverse cases, and verify actual green-duration distributions rather than selecting only favorable runs.
- [ ] **Use competitive controls and isolate the mechanism.** Keep fixed-24 as a diagnostic, but also tune fixed timing/splits on separate development plans and include a simple actuated comparator. Add experimental arms for fixed order with adaptive duration and adaptive order with constant duration. These isolate ordering and timing without changing the proposed controller. `fairness_priority` changes several rules together and is not a clean ablation. Keep phasing/clearance consistent across arms.
- [ ] **Define the workload and inference before collection.** Choose N/horizon to cover several load transitions; specify initialization, arrival cutoff, draining, and timeout handling. Analyze finite-workload clearance separately from sustained-flow performance. A time-limited study needs residual-queue logging. Retain/report all failures by scenario and arm; do not hide difficult cases through exclusions. Use independent plan-level differences and 95% confidence intervals, stratified by scenario; choose replication count from pilot variability and desired precision. Vehicle-level p-values are unsuitable as the main evidence because vehicles interact; the batch analyzer already uses plan means. [Wilcoxon assumptions](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html) still need checking.

### 3. Generate a small, reproducible publication package

- [ ] **Extend logging and analysis:** record decision-time counts, round/phase identity, selected and actual green duration, green end, queue traces, and actual arrival/crossing times. Current green-onset logs cannot fully reconstruct the final phase or explain every decision.
- [ ] **Produce two tables and three figures:** configuration/scenario table; results table with independent-plan counts, failures, absolute effects and confidence intervals; delay-effect plot across demand/skew; per-approach mean and tail-delay plot with service gaps; mechanism plot showing green-bound frequency, green utilization, and ablation effects. Report stopped delay as the primary endpoint, p95 delay and worst-served approach as safeguards, and clearance time separately. With fixed N, `N / completion_time` is a transformation of completion time, not independent corroboration or a capacity estimate.
- [ ] **Archive and position the contribution:** preserve plans, full configuration/code revision, dependencies, raw logs, analysis and figure commands outside the currently ignored-only `data/*` workflow. Compare with relevant queue-based/actuated literature before claiming novelty. The useful contribution to aim for is a reproducible account of **when this simple scheduling rule helps, why, and at what fairness cost**. VANET communication is conceptual here; packet exchange, loss, and latency are not simulated.

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

**Reading:** the intersection discharges roughly 2.3× faster per lane than a
real one and has almost no startup lost time. This is the single largest
threat to any efficiency claim: greens are cheaper here than in reality, which
systematically favours whichever controller grants more green. It does not
invalidate a *paired* comparison — both arms discharge alike — but it does
invalidate absolute throughput and delay figures, and it may change the sign
of an ordering effect near capacity. Calibrating headway and startup loss is
now the top model task, ahead of collecting results.

## Implementation checkpoint — 10 September 2026

**First step completed.** `python3 -m unittest discover -s tests -v` passes 16 tests, including duplicate/missing IDs, malformed plans/metadata, attribute mismatches, nonfinite measurements, provenance changes, ordinary-log compatibility and driver preflight. Sampler equivalence still passes all 36 combinations. Two sequential real simulator processes completed an N=1 fixed/fixed smoke test using SDL's dummy display; their logs passed the gate with one matched vehicle. Temporary fixtures/smoke outputs were written under `/tmp`; historical `data/` was not inspected or modified. This is a logging check, **not** timing or model validation.

**Compatibility:** old paired logs lack required provenance/attributes and will now be rejected; keep them as historical evidence and generate fresh runs. Vehicle-level p-values are no longer emitted as inference; batch tests continue to use plan means. Independence across plans and the final statistical protocol still need validation.

**Next step:** instrument and define timing/model acceptance checks before the windowed N=500 fixed/fixed repeats, then fixed/priority. Record actual last-crossing time separately from display drain, phase durations, release times and FPS windows. Use fresh plan IDs and keep every failed run. The 5% average-FPS and 250 ms drift thresholds remain provisional; passing the current gate does not establish simulation fidelity. After timing/model validation, freeze the experimental protocol before collecting publication results.
