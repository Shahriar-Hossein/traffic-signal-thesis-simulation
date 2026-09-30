**Publication readiness review — 1 October 2026**

Author-side assessment using an IEEE reviewer perspective; this is not an official IEEE review or an acceptance prediction. Scope: the current paired simulation study, especially [BATCH_ANALYSIS.md](BATCH_ANALYSIS.md), its raw collection, analysis code, and validation evidence. Historical thesis results are excluded.

**Recommendation: start writing now; do not treat the study as submission-ready yet.**

You have enough data for a meaningful Methods and Results draft, approximately six useful figures, and several supporting tables. The interesting result is that the priority controller reduces average stopped delay under these scenarios while sometimes worsening particular approaches and the upper tail. That is a more defensible paper than a claim that priority control always improves traffic.

The remaining work is principally about the credibility and scope of the contribution, not collecting more numbers to fill pages. I would request substantial additional evidence before supporting a research-journal submission. A narrowly scoped simulation paper may require less additional experimentation, but it still needs a clear contribution, adequate comparisons, and a justified treatment of timing and exclusions. Venue-specific expectations must be checked after choosing a target.

IEEE Access, for example, evaluates contribution, technical soundness, sufficient methodological detail, relevant references, and conclusions supported by evidence. These are useful review criteria here, not a universal checklist for every IEEE venue. [IEEE Access reviewer guidelines](https://ieeeaccess.ieee.org/reviewers/reviewer-guidelines/)

| Question | Assessment |
|---|---|
| Can I move on to writing? | **Yes.** Draft the study definition, controller, experimental design, results, and limitations now. |
| Is there enough data for graphs and charts? | **Yes.** Raw vehicle, phase, timing, and plan records support the figure set below. |
| Can I submit with the present conclusions unchanged? | **Not recommended.** Correct the analysis narrative and resolve the main validity and comparison concerns first. |
| Must I automatically increase every scenario to 30 or 50 seeds? | **No.** Replication should follow the precision required for the claim. More seeds cannot repair a weak baseline or systematic simulation bias. |
| Does `publication_eligible=true` establish publication readiness? | **No.** It records passage through the repository's programmed gates, not novelty, physical validity, or editorial acceptance. |

**Evidence checked during this review.**

The main collection is `data/study_collection_20260929/`: 100 planned experiments across five environments, with fixed12, fixed24, and priority in each experiment. It contains 300 vehicle logs and corresponding phase, signal, and metadata files. The analyzer reproduces **86 valid plans**, no duplicate replicates, and no incompatible-cohort errors at FPS tolerance 10% and release-drift tolerance 250 ms.

The valid subset represents 258 arm runs and 26,099 prescribed vehicles replayed in each arm: 78,297 vehicle outcome records. The statistical sample remains **13–20 plans per environment**, not 78,297 independent observations. Seeds 401–420 are reused across environments; do not present 86 as an independent sample for one pooled effect.

| Environment | Valid / planned | Vehicles per plan | Arrival schedule | Direction probabilities |
|---|---:|---:|---|---|
| Balanced moderate | 20 / 20 | 240 | 2 vehicles/s for 120 s | 25% each |
| One busy | 20 / 20 | 240 | 2 vehicles/s for 120 s | Right 85%; others 5% each |
| Two busy | 18 / 20 | 240 | 2 vehicles/s for 120 s | Up/down 35% each; right/left 15% each |
| High–low–high | 13 / 20 | 383 | 4, 0.5, 4 vehicles/s; 45 s each | 25% each |
| Sustained high | 15 / 20 | 480 | 4 vehicles/s for 120 s | 25% each |

These are offered rates across the intersection, not rates per approach or measured capacities. Arrivals occur at fixed intervals within each segment; seeds randomize vehicle attributes, directions, lanes, and turns. The 383 count follows the implemented segment-boundary convention. See [scenario generation](../scripts/make_plan.py), [plan construction](../core/plan.py), and [configuration](../config.py).

Verification performed:

- `python3 -B -m unittest discover -s tests`: **113 tests passed, exit 0**. Tests use temporary fixtures; no new simulation was collected.
- Recomputed the batch at 10% and 5% FPS tolerances using `write=False`.
- Independently inspected all **1,252 priority phase records**: no green mismatch against the full-precision coded rule and no selection below the highest logged weight among unserved approaches. Four-phase rounds contained all four directions. This checks recorded decisions, not independent sensor truth or road realism.
- Checked source definitions of stopped delay, crossing time, controller weights, phase timing, and uncertainty. A sampled collection metadata record's source-file hashes match current files; the batch also passes its within-study provenance/cohort checks.

The current reviewed Git revision is `8ec1815`. The working-state document's opening reference to `b3a5c65` is stale. Existing documentation and data were not edited; this report is the only added project file.

**What the results currently support.**

The following absolute values were recomputed from the valid subset. They are equally weighted means of the per-plan arm summaries, in seconds; tiny differences from displayed deltas can arise from rounding.

| Environment | n | Fixed12 mean stopped delay | Fixed24 mean stopped delay | Priority mean stopped delay | Priority − fixed12, 95% CI |
|---|---:|---:|---:|---:|---|
| Balanced moderate | 20 | 24.95 | 37.97 | 20.77 | −4.18 [−4.64, −3.74] |
| One busy | 20 | 67.96 | 60.91 | 21.11 | −46.85 [−47.97, −45.64] |
| Two busy | 18 | 27.88 | 40.26 | 20.15 | −7.72 [−8.78, −6.66] |
| High–low–high | 13 | 28.99 | 41.43 | 28.29 | −0.70 [−1.22, −0.16] |
| Sustained high | 15 | 42.28 | 46.60 | 38.77 | −3.51 [−4.27, −2.82] |

These are pointwise percentile-bootstrap intervals using 10,000 resamples and seed 20260910. They quantify plan variation within the accepted sample, not uncertainty about model fidelity or excluded plans.

The strongest observed mean-delay effect is under the 85%-right demand pattern. The weakest is high–low–high against fixed12. Priority wins on mean delay in 9/13 of those plans and loses in 4/13; it wins in every accepted plan in the other four environments against fixed12. There are no exact mean-delay ties at the analyzer's reported precision. All accepted plans favor priority on mean delay against fixed24. Clearance still has individual-plan losses, as the existing batch table correctly shows.

The high–low–high result should be central to the discussion: the mean improves by only 0.70 s against fixed12, while the mean of within-plan p95 delays worsens by **6.44 s [5.19, 7.63]**, with deterioration in 13/13 plans. Down and left also worsen. Service once per round does not guarantee equal delay or a bound on every vehicle's wait.

An appropriate provisional claim is: “In a simplified four-approach model with scheduled finite demand, the tested weighted-demand controller reduced mean stopped delay relative to two specified uniform fixed-time settings, with scenario-dependent approach and tail-delay costs.” It does not establish superiority over optimized fixed-time or actuated control, road capacity gains, VANET performance, or deployment readiness.

**Corrections and qualifications for BATCH_ANALYSIS.md.**

1. **One factual error needs correction before its text enters a paper.** The fixed24 approach paragraph lists “one_busy ... right” as not distinguishable from zero. Reanalysis gives **−44.763 s [−45.836, −43.696]** for that approach. All four one-busy approaches improve against fixed24 at the reported pointwise interval level. The stated high–low–high right loss and sustained-high right uncertainty are reproduced.
2. The main mean-delay, clearance, and fixed12 approach tables reproduce to their displayed precision. “Priority lowers mean delay and clearance in every environment” must mean the environment-level averages among accepted plans, not every run or every approach.
3. “CI crossing zero” does not establish equivalence or absence of an effect. Prefer “the interval includes both improvement and deterioration.” Intervals excluding zero across many endpoints are not automatically simultaneous or multiplicity-adjusted findings.
4. Add absolute arm outcomes alongside differences, and explicitly tabulate wins, ties, and losses. A reader needs to know whether a 4 s change starts from 10 s or 100 s.
5. The reference to “the lost-time finding” has no identifiable supporting analysis in the current Markdown documents. The current data may support descriptive phase-overhead analysis, but the causal mechanism remains unresolved.
6. Describe p95 precisely: the batch summarizes differences in each plan's within-arm 95th percentile. It is neither the 95th percentile of paired vehicle differences nor a pooled p95 across all environments.

**Main publication concerns and how to address them.**

**Timing validity is the most important internal-validity concern.** Vehicle motion uses pixels per rendered frame, while arrivals and phase timing use elapsed time. A change in rendering rate changes effective vehicle motion relative to signal service. Matching FPS within 10% is a screening rule; it does not demonstrate negligible bias in stopped delay, especially for a 0.70 s effect. Five plans ran concurrently, although each plan's controller arms were sequential. Core pinning helps resource isolation but does not establish outcome invariance. The default arm sequence also leaves run-order effects unseparated from controller identity. See [vehicle movement](../models/vehicle.py), [phase timing](../core/phase.py), [runner](../run_paired.py), and [simulation notes](SIMULATION_IMPROVEMENTS.md).

The stricter reanalysis is reassuring about the broad mean-delay pattern:

| Environment | n at 10% FPS gate | n at 5% gate | Priority − fixed12 at 5%, 95% CI |
|---|---:|---:|---|
| Balanced moderate | 20 | 20 | −4.180 [−4.638, −3.738] |
| One busy | 20 | 18 | −46.751 [−47.992, −45.427] |
| Two busy | 18 | 17 | −7.740 [−8.846, −6.610] |
| High–low–high | 13 | 9 | −0.716 [−1.275, −0.079] |
| Sustained high | 15 | 11 | −3.472 [−4.261, −2.773] |

There are **75 accepted plans** at 5%; all five mean-delay intervals against fixed24 also remain below zero. However, safeguard interpretations can change: sustained-high p95 against fixed12 becomes +2.267 s [0.194, 4.575], compared with +1.498 s [−1.641, 4.574] at 10%. This is a subset sensitivity check, not a correction for FPS bias or missing data.

Before submission, justify the FPS tolerance using outcome-level repeatability/load-sensitivity evidence, with isolated sequential runs and controlled or counterbalanced arm order. Repeated runs of the same plan measure execution variability; they do not add independent traffic plans. If motion or clock code is changed, validate the new version and collect new evidence rather than mixing its results with this archive.

**Exclusion handling needs a stronger audit trail.** Losses are concentrated in high–low–high (35%) and sustained high (25%). Estimates therefore describe the accepted plans; whether excluded plans systematically differ is unresolved. Compare planned approach counts, vehicle mix, and other pre-outcome demand characteristics between retained and excluded plans. Report when and why the FPS tolerance changed, how earlier attempts were retained or superseded, and how the final run was chosen. Do not assume failures are harmless because some threshold exceedances are numerically small. See [STUDY_EXCLUSIONS.md](STUDY_EXCLUSIONS.md).

The three green-rule exclusions need separate treatment from execution-timing failures. The full-precision audit confirms the coded rule, while one phase retains the documented floating-point floor quirk. Raw-data immutability does **not** prohibit a separately versioned, justified correction to an analysis checker. A later analysis could reconsider those plans under a corrected gate, subject to every other check, without overwriting original decisions. Such a reanalysis must distinguish the implemented floating-point rule from the intended exact-arithmetic formula. This review leaves the original 86-plan set unchanged. See [PRIORITY_RULE_RECHECK.md](PRIORITY_RULE_RECHECK.md).

**The baselines limit the contribution.** Fixed12 and fixed24 are two settings of the same uniform controller. In the one-busy scenario, 85% of demand is on one approach while a full fixed cycle allocates equal green to all approaches. The large improvement is useful evidence for this comparison, but it does not answer whether the method beats a demand-informed fixed split or a conventional actuated controller.

For a stronger controller paper, add a fixed-time baseline with cycle/splits selected on development plans and at least one relevant established demand-responsive baseline. Freeze tuning before fresh evaluation. Do not choose settings using the best outcomes on the present test collection and then call that collection held out. Existing research already compares Webster, max-pressure, and self-organizing controllers with explicit parameter evaluation; use it to frame baseline choices, not as proof that this controller is equivalent to those methods. [Genders and Razavi, An Open-Source Framework for Adaptive Traffic Signal Control](https://arxiv.org/abs/1909.00395)

**The mechanism and novelty are not yet established.** Priority changes both approach ordering and green duration. Two useful ablations are fixed order with adaptive duration, and demand order with a fixed duration, under consistent phase-transition rules. They would help separate scheduling effects from duration allocation and phase overhead. These require new experiments; the three existing arms cannot identify the separate causal contributions.

The 5 s yellow duration is shared, but the number of phases and the fraction of time consumed by transitions can differ. Plotting those quantities is possible now; attributing all benefits to reduced lost time is not. Real traffic-engineering lost time includes startup and clearance components and should not be equated automatically with total yellow seconds. [FHWA Traffic Signal Timing Manual, Chapter 3](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter3.htm)

Write a related-work comparison that identifies the specific contribution beyond established queue-responsive control. A credible candidate is a transparent paired evaluation of efficiency–fairness trade-offs in a constrained model. Whether that contribution is sufficiently original remains unestablished by this review's targeted literature check; a current, focused literature review is still required.

**The model supports a restricted simulation claim.** The controller's “queue” is actually all uncrossed vehicles in an approach, including moving and off-screen vehicles. Weights are inverse configured pixel-per-frame speeds. This is ideal access to simulator state, not a validated roadside detection system or calibrated passenger-car equivalence. Explain that assumption and the coefficient/bounds explicitly. See [weighted counts](../utils/counters.py), [green rule](../core/policy.py), and [lane observations](../core/observations.py).

The main runs have only 120–135 s of scheduled demand, begin with 10 s all-red accumulation, and continue until the last prescribed vehicle crosses its stop line. Thus this is a finite-demand transient study. “Clearance time” is elapsed time to the last stop-line crossing, not the time the whole intersection becomes empty. Stopped delay is accumulated nonmovement before that crossing; it is not automatically standard total control delay or full-route travel time.

The fixed rotation is right → down → left → up, and the geometry is direction-specific. Large benefits for up could partly reflect startup/order/geometry interactions; the current evidence does not isolate them. Longer horizons and rotated demand/initial-order checks would strengthen generalization. For physical traffic claims, add empirical calibration and validation, or carefully bounded replication in an established simulator. Merely switching simulator names would not itself validate the model. FHWA explicitly separates error checking from calibration against observed system behavior. [FHWA microsimulation calibration guidance](https://ops.fhwa.dot.gov/publications/fhwahop18036/chapter5.htm)

**The statistical plan needs finishing.** Keep the plan as the replicate and analyze each environment separately. State the primary endpoint and how both fixed comparisons are handled. Treat approach and tail analyses as clearly labeled safeguards/exploratory estimates, or use a justified multiplicity procedure for confirmatory claims. Bootstrap CIs with 13 plans can be informative, but do not guarantee precision or correct small-sample coverage.

Define a smallest useful improvement using an external engineering or application rationale. Because these effects have already been examined, a threshold chosen now is post hoc and must be labeled accordingly; it cannot be represented as preregistered. For illustration only, a 1 s required reduction would not be established by high–low–high's −0.70 s estimate and [−1.22, −0.16] interval. Do not select a threshold merely because it makes the observed result look favorable. A new confirmatory study should freeze endpoints, thresholds, exclusions, tuning, and the stopping rule before collection.

**A practical figure and table set from the existing data.**

No dedicated figure-generation pipeline was found, and no root-level `batch_comparison.json` is currently archived for this collection. Per-plan outputs and raw logs exist, so publication figures are feasible, but still need reproducible export/plot code and an explicit analysis manifest. No new simulation is needed for the following core set.

| Figure | Question answered | Existing source and presentation |
|---|---|---|
| 1. Study design and demand schedule | What was compared? | Controller schematic and scenario schedules from plans; distinguish randomized attributes from fixed arrival times. |
| 2. Mean-delay effect forest plot | Where does priority help? | Two contrasts × five environments, plan-bootstrap intervals, zero reference, and n. Include plan points if space permits. |
| 3. Clearance effect plot | Does the finite workload finish earlier? | Last-stop-line-crossing differences and intervals; show individual-plan losses. |
| 4. Approach-delay heatmap | Who benefits and who pays? | Five environments × four approaches, separate baseline panels; supply CIs in an adjacent table or interval plot. |
| 5. Mean-versus-tail trade-off | Is a mean gain bought with worse long waits? | Per-plan mean-delay and p95 differences; prominently include high–low–high and sustained high. |
| 6. Controller behavior | What did the controller actually do? | Selected-green distributions, phase counts, and a transparently selected phase timeline; account for censored final phases. |
| Supplement: timing and exclusions | How sensitive are conclusions to acceptance rules? | FPS/drift plots, exclusion counts/reasons, and the 5% versus 10% sensitivity table. |

Useful tables are: scenario/model/controller settings; absolute outcomes plus paired effects; complete approach/tail safeguards; and inclusion/exclusion accounting. A conference paper may combine panels to fit its page limit. Six figures are a suggested narrative, not a publication requirement.

Use the same accepted plans for each displayed paired comparison. Keep seconds and delta signs explicit, show n per environment, use readable vector exports, and avoid vehicle-level error bars that imply independent vehicles. If displaying pooled vehicle distributions, label them descriptive and use plan resampling for uncertainty. A representative run should be selected by a stated rule, not because its improvement looks largest.

Additional cumulative arrivals and stop-line crossings can be reconstructed from timestamps. Their difference measures released-but-uncrossed inventory, including moving vehicles; it is not a continuous stopped-queue trace. Phase queue snapshots likewise do not justify interpolated continuous queue claims. The present data do not establish emissions, fuel savings, safety improvements, network communications performance, or calibrated road capacity.

**What to do before submission, in order.**

1. **Start the draft and choose the claim.** Use the restricted simulation claim above; define the contribution and target venue before expanding the experiment indiscriminately.
2. **Finish the analysis package using existing data.** Correct the fixed24 narrative in the eventual manuscript, produce the proposed figures, include absolute outcomes and all safeguards, preserve the 5% sensitivity analysis, and document exclusions and the rounding issue. Archive the exact analysis settings and included-plan list alongside a versioned export.
3. **Resolve execution bias.** Provide outcome-level timing/repeatability evidence. If that fails, repair the simulator and collect fresh evidence under the new version.
4. **Strengthen the claim with appropriate experiments.** For a controller-superiority or mechanism paper, prioritize a credible tuned baseline and ablations over simply adding seeds to the same comparison. For broader traffic claims, add model-validation evidence and demand/horizon robustness checks.
5. **Freeze the final protocol and evidence release.** Justify precision requirements, disclose exploratory decisions, preserve raw archives and source/runtime identities, and provide reproducible analysis instructions. Code in Git alone is insufficient because `data/` is ignored. Keep the historical thesis separate.

The next actionable step is to write a one-paragraph contribution statement and draft Methods/Results from the current evidence while preparing the timing-validation and baseline plan. The main unresolved question is whether the observed benefits remain convincing under a credible comparator and execution conditions shown not to distort the measured effects.

**Reproduction note.** The following reproduces the two batch selections without writing results into the evidence folders; run from the repository root. Original raw files and comparison decisions remain untouched.

```python
from analyzers.analyze_paired import analyze_batch

for tolerance in (0.10, 0.05):
    result = analyze_batch(
        "data/study_collection_20260929",
        fps_tolerance=tolerance,
        drift_tolerance_ms=250.0,
        write=False,
    )
    print(tolerance, result["plans_valid"])
    print(result["per_scenario"])
# Valid plans: 86 at 0.10; 75 at 0.05.
```
