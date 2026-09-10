# Claude handoff: commit review and required corrections

Review date: 10 September 2026. Reviewer: Codex. Audience: Claude continuing this project.

Reviewed range: **`bad2f64ddc800b0023ffb47dda2a59dff410db70` through `9de68a9c29615590e674a54185d63ffedd7b7b83`, inclusive: 38 commits.** The endpoint was HEAD when review began. `6edde75` arrived during review and is discussed separately below. Locations refer to the reviewed source; use the named functions if subsequent edits move lines.

The user requested a review document only. No implementation, tests, configuration, or archived results were changed by this review. Do not interpret this document as evidence that fixes have already been made.

## Review decision

**Request changes before relying on the pipeline for evaluation collection.** The important problems are measurement integrity, experimental grouping, and reproducibility. Reducing line count is useful when it removes competing definitions of behavior; it is not a substitute for fixing those problems.

The work has useful foundations: strict vehicle identity checks, rejection of nonfinite waits, plan-level rather than vehicle-level inference, sequential arms, preserved raw data, and explicit limitations on the pilot. Retain those. However, several comments and completion checkmarks promise stronger guarantees than the implementation provides.

I ran `python3 -B -m unittest discover -s tests -v`: **57 tests passed**. I also ran temporary synthetic probes and read-only reanalysis of the committed pilot. Passing tests currently coexist with the failures below. In particular, the supposedly valid fixture in `tests/test_paired_validity.py` contains inconsistent timing metadata and an incomplete phase row; it cannot serve as the reference for a complete audit contract.

Priority definitions: **P1** affects whether experimental evidence is valid or faithfully reproduced; **P2** is a concrete correctness or diagnostic issue to resolve before the affected feature is relied upon. Design improvements are listed separately from confirmed bugs. No P0 finding.

## Findings

### R1 — P1: the scenario key collapses the demand-regime axis

**Commits:** `1ccac00`, integration missed in `2fb44a7`/`adb05ef`; safeguards added by `a7ac06e`.
**Locations:** `analyzers/analyze_paired.py:597`, `analyze_batch()` around lines 677–737.

`scenario` is only `uneven_mode + target_vehicle_count`. Low, medium, high, and mixed plans with the same skew and N all become `even_500`. Running the advertised twelve-cell grid therefore produces only three scenario strata. `invalid_by_scenario` also loses the regime. Additionally, safeguards are attached only to `per_contrast`, never to `per_scenario`, so even after correcting the key the per-cell primary estimate will lack its per-cell safeguards.

**Observed:** synthetic headers with all four values of `pinned_condition` each report `even_3`. This was a classification probe; changing headers alone does not make a new valid replay.

**Required correction:** centralize a structured scenario identity containing skew, pinned regime (explicit `mixed` for absence/None), and workload. Use it in pair summaries, batch grouping, and failure counts. Aggregate primary and safeguard endpoints through the same grouping path. Do not claim a heterogeneous overall mean is the per-scenario result.

**Acceptance:** construct valid pairs in all twelve cells; obtain twelve strata, each with its own safeguards and failures. An old plan without the pin field maps to mixed without changing its stored hash.

### R2 — P1: the validity gate trusts summaries that contradict raw timestamps

**Commits:** `4dcd990`, `0e82b47`, `eb85469`; fixture coverage in `8647c3b` and subsequent tests.
**Location:** `analyzers/analyze_paired.py:213`, `check_validity()`.

The gate checks individual fields but omits the relationships that establish their meaning. On the existing valid fixture, each of these independent mutations still returns `valid=True`:

| Mutation to fixed arm | Contradiction accepted |
| --- | --- |
| First `released_sec = 5` | Five-second lateness despite the 250 ms limit and metadata claiming 2 ms maximum |
| First `crossed_sec = 1000` | Crossing after the declared 60-second run |
| First `wait_time_sec = 1000` | Stopped delay greater than the vehicle's entire release-to-crossing interval |
| `frames_total = 1` | 60 FPS over 60 seconds despite only one frame |

The fixture's own `last_crossing_sec=58.5` is unrelated to its maximum raw crossing time, yet passes.

**Required correction:** derive clearance and release lateness from the rows; check them against sidecar values and tolerances. Enforce release ≤ crossing ≤ run end and stopped delay ≤ travel time with documented rounding tolerances. Validate frame counts as integers and reconcile frame count/duration with reported average FPS. Choose one authoritative release timestamp: the generator currently measures drift before construction, while `Vehicle` records a later timestamp. Account for that deliberately rather than demanding impossible exact equality between different events.

**Acceptance:** all four mutations are rejected with specific reasons and no effects. A coherent fixture and real archived rows survive appropriate precision allowances. Test boundary rounding, not just missing keys.

### R3 — P1: the final phase is lost on successful shutdown

**Commits:** `52d66ca`, inherited by `e522a1e`; affects `ca5302c`, `c40086d`, `75c6cb3`, and recorded results.
**Locations:** `core/cycle_fixed.py:71`, `core/cycle_priority.py:89`, `core/cycle_fairness_priority.py:91`, `core/cycle_ablation.py:103`; `main.py:206` shutdown.

Phase records are written only after the entire green and yellow finish. The controller is a daemon thread. Successful count-mode shutdown occurs 1.5 seconds after the final crossing, frequently before that phase ends, and there is no finalization barrier. The very phase that completed the workload disappears from timing and discharge reports.

**Observed in the committed pilot:** all 16 arms have exactly one more signal-change row than phase row. For `even_500_seed304/fixed`, there are eight signal onsets but seven phase rows; all **43** crossings classified as outside green occur after the last logged green. For `seed302/fixed`, the corresponding count is **18**. This is not evidence that those vehicles crossed illegally: the final green is missing. The analyzer's suggestion that outside-green crossings are mostly yellow crossings is unsupported here.

**Required correction:** persist phase onset/decision immediately and record end transitions independently, or maintain a synchronized active-phase record that shutdown finalizes once with an explicit truncation status. Do not wait out the nominal phase and thereby alter workload completion. Distinguish a censored final phase from a completed phase in duration/overrun calculations. Check phase-log completeness before presenting model-validation measurements.

**Acceptance:** terminate during green, during yellow, and after an ordinary phase boundary. Every served phase is represented exactly once, completed records have valid transitions, and final-green crossings are attributable. Test the actual controller/shutdown interaction with a fake clock. Reissue corrected derived reports as a new analysis version; preserve the old raw archive.

### R4 — P2: phase logging runs while the old approach is green again

**Commits:** `52d66ca`, `e522a1e`.
**Locations:** `core/cycle_priority.py:87`, `core/cycle_fixed.py:69`, `core/cycle_ablation.py:101`, and the equivalent fairness path.

At yellow completion, `currentYellow` becomes zero before `log_phase()` performs synchronous file I/O, while `currentGreen` still names the old approach. `Vehicle.move()` uses those two fields for permission to move. Thus the old approach is green again during that write and subsequent bookkeeping/reordering, outside its recorded green interval. The pre-existing transition ordering already had a gap; adding disk I/O expands it. At onset, permission also changes before the recorded `green_start` and, in priority, before the duration snapshot.

**Required correction:** define one phase-transition operation so state and event timestamps describe the same transition, with no blocking logging in an unintended movement-permission state. Preserve the intended phasing explicitly; do not silently add a new all-red duration as a refactor. Capture a decision before exposing its green.

**Acceptance:** block the logging sink deliberately and inspect movement permission during every transition. No vehicle receives an unrecorded extra green because a disk write is slow. This review established the state path by inspection; it did not measure the size of this effect on the pilot machine.

### R5 — P1: recording an FPS series is not gating its timing

**Commits:** `eb85469`, `ca5302c`.
**Locations:** `analyzers/analyze_paired.py:259,343`; `main.py:261`; `analyzers/analyze_timing.py:126`.

The gate compares only average and minimum FPS. Two series `[30,60,60]` and `[60,60,30]`, with equal summary values, pass. Their physics slowed during different intervals. The timing analyzer displays window divergence but no acceptance result feeds back into pair validity. Removing both phase logs also leaves the pair valid, so severe or unmeasured controller-clock slippage cannot be rejected by the advertised timing acceptance path.

Window samples have no actual start/end timestamps; each window closes when a rendered frame finally arrives. Comparing sample index alone does not establish alignment after a stall. Partial final windows and setup time further complicate coverage.

**Required correction:** define the timing acceptance contract before calling this feature an acceptance report. Record window boundaries and compare compatible elapsed intervals, or implement a justified fixed-step physics contract. Give missing coverage, stalls, and phase timing explicit dispositions; propagate rejection/insufficient evidence to the report used for collection. Different controller phase sequences must not themselves count as clock faults.

**Acceptance:** equal means/minima with differently timed stalls cannot pass solely because the extrema match; missing/truncated telemetry is explicit. Thresholds should come from the agreed experiment protocol, not be invented to make current fixtures pass.

### R6 — P1: batch inference can combine duplicate plans and different experiments

**Commits:** `1ccac00`, `ca7a407`, `a7ac06e`; builds on the pair-only provenance gate.
**Locations:** `analyzers/analyze_paired.py:658–725`.

Provenance is checked between arms of one pair, not across the pairs pooled into an interval. Contrast identity is just the two folder labels. Copying a valid plan directory to a second name makes it count as two independent plans. Changing both arms' configuration in one pair and recomputing their fingerprints still permits that pair to be pooled with a different-configuration pair. Likewise, labels alone do not guarantee stable controller assignments across plans.

**Observed:** copying the fixture reports two valid plans and `plans=2`. Giving one of those pairs a different internally consistent configuration still reports two valid plans. All pilot arms currently share one source fingerprint, so this is an exposed aggregation defect, not evidence that the committed pilot mixed implementations.

**Required correction:** validate study/cohort identity before aggregation: intended controller mapping, simulation/configuration provenance, analysis settings, scenario, and independent replicate identity. Reject duplicate archived plan hashes; account for repeated seeds/renamed plans using an explicit replicate definition, since `plan_id` itself contributes to the existing hash. A directory glob is a selection convenience, not an experimental identity check. Reused seeds across regime cells also mean a pooled overall CI cannot assume those observations are independent.

**Acceptance:** duplicates, incompatible configurations, and changed controller assignments produce clear cohort errors or separate explicitly labeled cohorts. Genuine independent plans still aggregate. Repeated runs of one plan are not promoted to independent plans by renaming folders.

### R7 — P2: mixed and pinned regimes do not preserve vehicle draws

**Commits:** `2fb44a7`, repeated as a guarantee in `373d69d` and `f15b13c`.
**Locations:** `core/plan.py:183–190`; `docs/EXPERIMENT_PROTOCOL.md:60`; `tests/test_scenarios.py:27`.

The same RNG draws traffic conditions and vehicle attributes. Pinned plans skip the condition draw, while mixed plans consume it initially and on transitions. The comment that skipping a draw cannot shift the stream relative to an unpinned plan is incorrect. Existing tests compare high against low only.

**Observed:** `build_plan(301, 500, 'even', condition='high')` versus its mixed counterpart differs in vehicle attributes at **494 of 500** sequence positions. Seed 5 happens to match for the 40-vehicle test size, but differs at eight positions at N=500, starting at seq 60. Some seeds therefore conceal this error in small fixtures.

**Required correction:** either narrow the documented guarantee to comparisons among pinned regimes, or version the generation scheme and separate demand RNG from vehicle RNG/use one precomputed vehicle stream across all regimes. Preserve old plans and their hashes; do not silently regenerate their traffic under a changed sampling algorithm.

**Acceptance:** test pinned versus mixed at multiple seeds and across condition transitions if retaining the cross-regime guarantee. Existing archived plans remain readable with unchanged identities.

### R8 — P2: plan validation does not verify the condition actually replayed

**Commits:** `bad2f64`, `2fb44a7`, `17abf85`.
**Locations:** `core/plan.py:313–354`; `core/generator.py:135`.

The pin is checked against the timeline but vehicle conditions are only checked for membership in the rate table. The replay actually uses each vehicle's condition. A signed high-pinned plan whose first vehicle says low is accepted. More generally, timeline and vehicle conditions can disagree, and a rate label does not guarantee offsets implement that rate. Hash integrity proves the supplied document is unchanged; it does not establish semantic agreement among these fields.

There is also an error-path bug: `pinned_condition=[]` reaches dictionary membership before the string type check, raising `TypeError` instead of the loader's intended `ValueError`. The main CLI catches only the latter.

**Required correction:** validate vehicle condition against the active timeline event and pin. Define whether arbitrary prescribed arrival schedules are allowed; if allowed, do not certify their nominal demand rate merely from a header label. Validate types before hash-table membership. Reuse the existing skew validator for loaded mode names if the schema promises supported skews.

**Acceptance:** rehashed contradictions are rejected, not just tampered hashes. Malformed pin types produce ordinary plan-validation errors. Valid legacy mixed timelines remain accepted.

### R9 — P2: diagnostics can crash on precisely the invalid arms they must report

**Commits:** `ca5302c`, `cb4f695`, `c40086d`, `1206986`.
**Locations:** `analyzers/analyze_timing.py:59,149`; `analyzers/analyze_discharge.py:92`; `scripts/export_results.py:79`.

`load_arm()` accepts syntactically valid JSON metadata that is a scalar or list. The pair gate rejects it, but timing/discharge call `.get()` without the gate's type guard. Replacing the fixture sidecar with JSON `3` makes `analyze_timing(..., write=False)` raise `AttributeError: 'int' object has no attribute 'get'`. `run_pair()` always calls timing after reporting validity, and export always calls all analyzers, so malformed evidence can abort diagnosis or leave a partial package.

Phase numeric parsing also accepts NaN/infinity, and missing/bad phase rows disappear without an explicit completeness result. In timing contrasts, absent clearance is converted to zero, creating an invented numeric difference.

**Required correction:** return one normalized load result with structured errors, then let each analyzer state which measurements remain available. Reject nonfinite measurements at parsing boundaries and preserve missing quantities as null. Diagnostics should work on failed runs without silently presenting them as complete. Stage exports and finish them atomically so analysis errors do not leave something resembling a complete package.

**Acceptance:** scalar/list/null metadata, malformed FPS arrays, nonfinite phase values, incomplete phase logs, and missing clearance produce serializable diagnostic reports without tracebacks or fabricated zeros. Exercise the driver and exporter paths, not only `analyze_pair()`.

### R10 — P1: export does not preserve the analysis contract or identify run code

**Commits:** `1206986`, `8713465`; provenance introduced in `bb40ef4`.
**Locations:** `scripts/export_results.py:59–87,123–153`; committed pilot `manifest.json`.

Export recomputes comparisons with default tolerances and inferred baseline; it does not carry the explicit baseline/tolerances used for the original comparison. **Observed:** a fixture analyzed with `baseline='fixed'` exports with baseline `priority` when priority has the earlier recorded start time. This can reverse the contrast. The exported command entries are largely placeholders, not the exact run commands promised by the module docstring; runtime dependencies and the run environment are not recorded per arm.

The manifest's clean commit is the **export/analysis revision**, not proof of the simulation revision. In the actual archive, the first fixed arm's source fingerprints differ from manifest revision `17abf85` for `core/initializer.py`, `core/plan.py`, and `main.py`. That is not evidence of a bad pair: analysis legitimately happened later. It is evidence that one unlabeled revision is insufficient to replay the run. Startup fingerprints identify bytes but currently provide no explicit checkout recipe for those bytes.

**Required correction:** persist and export the analysis specification (baseline, tolerances, schema/method version, selected cohort). Distinguish run source revision/dirty state from analysis/export revision and verify the recorded fingerprints against retrievable source. Capture actual invocation and relevant runtime versions/environment at run time. Analyze the copied snapshot, not mutable source folders after copying. Preflight duplicate destination basenames and add file digests to the package manifest for integrity checks.

**Acceptance:** export preserves an explicit baseline and nondefault tolerances, labels revisions correctly, and can verify all copied inputs. A documented checkout/environment recipe reproduces the archived simulation source fingerprint. Later analysis revisions must not imply the run used later code.

### R11 — P2: historical headway predictions silently use today's configuration

**Commit:** `7a833e4`.
**Location:** `analyzers/analyze_discharge.py:24–59,159`.

`predicted_headways()` imports current `movingGap` and `speeds`, while `analyze_discharge()` reads a historical arm whose captured configuration already contains the relevant values. Sprite lengths are another hard-coded copy. Recalibrating the project changes the reported prediction for untouched archived data.

**Observed:** reanalyzing `even_500_seed301/fixed` gives a car prediction of 0.554 s. Patching only the analyzer's current gap from 15 to 182 gives 1.896 s for the same raw run. No archive bytes changed.

**Required correction:** derive the historical prediction from verified run configuration and recorded sprite geometry. If offering a counterfactual prediction under current settings, label it separately with its own configuration. Withhold historical predictions if required provenance is unavailable. Describe the simple geometry formula as a model prediction under stated following assumptions; it is not proof that mixed-speed/turning dynamics are fully explained.

**Acceptance:** changing live configuration or local sprites cannot change a historical prediction. Add a fixture whose captured gap/speed differs from the current config and assert the captured values are used.

### R12 — P2: discharge metrics overstate what the logged events measure

**Commits:** `c40086d`, `87850e1`, `c649d45`, `7a833e4`.
**Location:** `analyzers/analyze_discharge.py:97–153` and the model-measurement discussion in `PUBLICATION_READINESS.md`.

`green_utilisation_mean` averages `(last_crossing - green_start) / green_duration` only over greens with crossings. A single arrival just before green end yields almost 100% utilization even if the rest of green was empty, and entirely empty greens are excluded. This is time-to-last-crossing fraction conditional on serving someone, not the fraction of green actively used for discharge.

Similarly, three crossings anywhere across an approach do not establish a sustained queue, yet `saturating` uses that count as its qualification. The first crossing after onset includes approach travel when nobody was queued; it does not isolate startup lost time. The module claims residual queues are reported, but no residual-queue measure is returned. R3 additionally biases these metrics by deleting final phases.

**Required correction:** use precise descriptive names for what is currently observable, or collect per-lane queue/occupancy evidence needed for utilization, saturated discharge, and startup-loss estimands. Include empty greens where the definition requires them. Do not use these proxies as measured saturation capacity or startup lost time in calibration conclusions. No particular external benchmark value was verified in this review.

**Acceptance:** contrast a continuously queued green, one late isolated crossing, an empty green, and delayed first arrival without an onset queue. Reports must distinguish them rather than assign misleading utilization/capacity semantics.

### R13 — P2: identical phase order does not make onset gaps clock drift

**Commits:** `ca5302c`, partial fix `c68a605`, formatting `427ffb3`.
**Location:** `analyzers/analyze_timing.py:110–144`.

The new `fixed_order_adaptive_duration` controller deliberately shares fixed order with `fixed` while changing duration. The timing report still reports their accumulated onset divergence as the phase-onset comparison, under text describing clock differences. Matching order alone is insufficient; different granted durations produce different onsets by design. The code also calls an identical common prefix an identical order when one sequence has extra phases.

Bound frequencies are hard-coded at 6/24 for every controller, so the supported fairness controller's 18-second ceiling is never reported as its ceiling. Intentional early green termination in that controller is mixed into the generic actual-minus-selected overrun statistic.

**Required correction:** distinguish repeatability of the same controller/decision schedule from descriptive cross-controller schedule divergence. Use controller-specific recorded duration bounds and termination reasons, and name prefix comparisons honestly. Retain `n/a` for unmeasurable timing values.

**Acceptance:** fixed versus fixed-order/adaptive-duration with the same order does not imply a timing fault; fairness greens at 18 seconds count against their actual ceiling; partial prefixes are explicit.

### R14 — P2: non-95% sample-size requests use an unrelated constant

**Commit:** `bf98352`.
**Location:** `analyzers/analyze_paired.py:387–398`.

`plans_needed()` uses `sqrt(2)` for every confidence level except exactly 0.95. The parameter therefore silently promises unsupported results. **Observed:** `plans_needed(3, 1, 0.99)` returns **19**, whereas the function's own stated normal-approximation formula with the 99% quantile gives **60**. Current summary callers use the default 95%, so this does not change the verified pilot's 114-plan figure.

**Required correction:** use the standard-library call `statistics.NormalDist().inv_cdf((1 + confidence) / 2)` and validate finite inputs/confidence bounds, or remove the unsupported parameter and explicitly support only 95%. This is a case where one existing library call is more correct than the custom branch.

**Acceptance:** 90%, 95%, and 99% give increasing required counts and match the declared formula. Invalid inputs have defined behavior; no arbitrary fallback quantile.

### R15 — P2: the documented capacity classification contradicts the endpoint definition

**Commits:** `adb05ef`, `373d69d`, `f15b13c`; measurement claims in `87850e1`/`c649d45`.
**Locations:** `scripts/scenarios.py:14–20`; `docs/EXPERIMENT_PROTOCOL.md:56–58` and its later finite-workload discussion.

The scenario grid calls 0.5/2/4 veh/s below/near/over capacity because a single finite mixed-demand plan cleared 500 vehicles in 248 seconds. The protocol later correctly says `N / clearance_time` is not a capacity estimate. The same quantity cannot establish capacity earlier in that document. A balanced aggregate clearance figure also cannot certify capacity status for an 85/5/5/5 allocation under every controller.

**Required correction:** keep low/medium/high as offered-rate labels until capacity status is established under a defined sustained-demand/queue criterion, by approach and relevant control policy. Record provisional hypotheses separately from measurements. Correct the completed checklist claims for scenario validation and final-phase logging in light of R1/R3/R12. This does not require discarding the grid, just accurately specifying what its cells mean.

**Acceptance:** the scenario table states offered rates independently of unverified capacity labels; each asserted saturation classification cites an appropriate reproducible measurement. No new calibrated-traffic claim should be inferred from the existing pilot.

## Simplifications and test improvements

These are follow-up design requests, not a license to rewrite the simulator wholesale.

1. **Share the duration rule instead of testing a duplicated expression through AST inspection.** `e522a1e` adds `adaptive_green()` but leaves the original formula inline. `tests/test_controllers.py:34` extracts only the assignment to `green_time`, then supplies `vehicle_required_time = weight * 0.75` from the test itself. Changing the preceding coefficient in priority can evade the claimed drift protection. Put the pure rule in one dependency-light policy module, call it from both controllers, and test its externally specified cases directly. Archive the old implementation by revision; source duplication is not needed to preserve historical evidence.
2. **Share phase execution, retain explicit policies.** Fixed, priority, fairness, and ablation paths duplicate transition timing, yellow handling, log writing, and reset behavior. R3/R4 will otherwise require parallel fixes. A common phase executor with explicit decision data and termination semantics can serve these policies. First add behavioral tests for order, tie-breaking, one-service-per-round, duration, and shutdown. Do not infer equivalence from a callable registry or one duration expression.
3. **Use a real registry mapping.** `core/controllers.py` maintains `NAMES` and a matching if-chain separately. A name-to-module/function mapping can define names and lazy resolution once without importing pygame into analyzers. This is a modest cleanup, not a performance claim.
4. **Fix the builder's default identity at its source.** `core/plan.py:216` calls `default_plan_id()` without `pinned`. Direct `build_plan(5,40,'even',condition='low')` and `condition='high'` both produce `even_40_seed05`, despite `default_plan_id()` supporting regime-specific names. CLI callers happen to work around it by constructing the ID first. Pass the pin in the builder and test the builder directly.
5. **Prefer straightforward standard-library operations.** `Counter(greens)` expresses the duration histogram without repeated `.count()` scans; `NormalDist.inv_cdf` fixes R14. Do not add a dependency or abstraction just to shorten otherwise clear code.
6. **Make a valid fixture physically and internally coherent.** Correct raw/summary timing relationships, realistic telemetry coverage, and complete phase records. Add negative cases by mutating that valid object. The current tests predominantly prove field presence and local formulas, not the promised end-to-end contracts.

### Relevant inherited limitations, not newly introduced defects

The stopped-delay accumulator in `models/vehicle.py:457` still uses `datetime.now()`, although release/crossing and run duration use a monotonic clock. A wall-clock adjustment can affect the primary endpoint without affecting the new timing telemetry. This predates the reviewed change to that file; treat it as an incomplete timing migration, not a newly introduced wait-calculation regression. Move duration measurement to the shared monotonic source if claiming timing is unified; keep wall time only for human-readable timestamps.

The paired driver's `--plans DIR` path also predates this range: it runs into `PAIRED_ROOT` but aggregates `args.plans`, so an external plan root is not necessarily the results root; its batch branch returns normally even with invalid pairs. Keep these on the orchestration backlog and test them before adopting that CLI for automated collection. They are not attributed to the new glob selector.

## Commit-by-commit disposition

“No additional finding” means no separate actionable problem was established for that commit; it is not a proof of correctness. Findings above describe the state at the review endpoint. Historical breakages repaired later are identified rather than reported as still open.

| # | Commit | Review disposition |
| --- | --- | --- |
| 1 | `bad2f64` validate plan structure | Good structural boundary; semantic timeline/vehicle agreement remains open (R8). |
| 2 | `bb40ef4` startup provenance | Useful detached configuration and content fingerprints; distinguish source identification from reproducible run revision (R10), enforce cohorts too (R6). |
| 3 | `4dcd990` fail-closed pair gate | Keep exact ID/attribute checks and removal of vehicle-level inference; cross-field validation remains incomplete (R2). |
| 4 | `409cf17` driver preflight | Existing-folder refusal and external-plan copy are useful; no additional new defect established. Shared plan validation needs R8. |
| 5 | `8647c3b` gate/provenance tests | Tests pass, but the valid fixture is internally inconsistent; expand behavioral contracts (R2/R5/R9). |
| 6 | `e7d1fe6` readiness checklist | Reasonable separation of engineering, model validity, and publication evidence. Subsequent completion claims need reconciliation. External thesis/literature assertions were not re-audited here. |
| 7 | `35fdebf` shared run clock | Improves run/release origin; primary stopped-delay clock remains an inherited migration gap. |
| 8 | `0e82b47` release/crossing timestamps | Correct direction for clearance and travel; reconcile raw timestamps and metadata (R2). |
| 9 | `52d66ca` phase decisions | Missing final phase and logging during unintended green are actionable (R3/R4). |
| 10 | `eb85469` FPS series | Series is recorded, but temporal comparability is not established by mean/minimum (R5). |
| 11 | `3c20406` phase-log discovery fix | Correctly repairs the preceding phase sidecar being mistaken for a second vehicle log. Do not reopen that fixed bug. |
| 12 | `ca5302c` timing report | Useful diagnostics, insufficient acceptance contract and malformed-input handling (R5/R9/R13). |
| 13 | `1ccac00` scenario intervals | Plan-level inference is appropriate in intent; regime grouping and cohort/replicate identity need R1/R6. |
| 14 | `fdd5ae8` tail/worst approach | Per-arm summaries reproduce; ensure safeguards accompany per-scenario inference (R1). No separate arithmetic defect established. |
| 15 | `c40086d` discharge report | Per-lane headway grouping is sensible; incomplete phases and proxy interpretation need R3/R12. |
| 16 | `cb4f695` automatic timing report | Correct place to expose diagnostics, but unconditional call can crash invalid-run handling (R9). |
| 17 | `87850e1` timing/discharge measurements | Qualify model metrics and capacity claims (R3/R12/R15). Repeatability seed201 raw evidence is not in the committed pilot package reviewed here. |
| 18 | `c68a605` differing-order onset fix | Repairs the obvious differing-order case; equal order with different durations remains (R13). |
| 19 | `427ffb3` n/a formatting | Good missing-value presentation; remaining zero substitution is in the underlying timing contrast (R9). |
| 20 | `75c6cb3` green distribution | Useful descriptive addition; histogram misses final phase and bounds are controller-specific (R3/R13). Optional Counter cleanup. |
| 21 | `1206986` results export | Preserve analysis settings and distinguish run/export provenance; harden failed-run exports (R9/R10). |
| 22 | `ca7a407` batch glob | Selection works; glob membership cannot replace cohort validation (R6). No separate selector bug established. |
| 23 | `2fb44a7` pinned regime | Pinned-only vehicle coupling works; mixed coupling, semantic validation, and builder IDs need R7/R8 and simplification #4. |
| 24 | `e522a1e` ablations/registry | Clean intended decomposition, but duplicated execution and weak rule-equivalence test need simplifications #1–3; inherits R3/R4. |
| 25 | `adb05ef` scenario grid | CLI wiring supplies regime IDs correctly; grid grouping and capacity labels need R1/R15. |
| 26 | `bf98352` replication planning | Default pilot count reproduces; nondefault confidence is incorrect (R14). Registry-aware gate is useful. |
| 27 | `373d69d` experiment protocol | Draft status and missing comparator caveats are appropriate; cross-regime sampling and capacity assertions need R7/R15. |
| 28 | `17abf85` legacy plans | Correctly repairs missing-pin compatibility without rewriting hashes. Type-check ordering still needs R8. |
| 29 | `8713465` archive pilot | Recomputed all eight pair effects and pooled summaries; primary numbers reproduce. Preserve raw evidence, annotate incomplete phases and export revision (R3/R10). |
| 30 | `e2f085c` archive byte attributes | Appropriate `results/** -text` protection; no additional finding. |
| 31 | `cc6c7d2` restore CRLF | Verified all 48 changed CSVs are identical after CRLF→LF normalization. No semantic row change found. |
| 32 | `3df26e3` replicated result | Mean −11.42 s and CI reproduce. Separate descriptive evidence from causal mechanism; see evidence notes below. |
| 33 | `f15b13c` completed checklist | Completion is overstated for final-phase logging, scenario stratification, cross-regime identity, and reproduction (R1/R3/R7/R10/R15). |
| 34 | `a7ac06e` pooled safeguards | Pooled arithmetic reproduces, but safeguards are missing per scenario and cohort checks remain absent (R1/R6). |
| 35 | `21834c6` safeguard results | Recomputed estimates, CIs, and counts agree; do not infer the individual-level mechanism from marginal summaries alone. |
| 36 | `c649d45` geometry explanation | Useful hypothesis about model parameters; prediction is not a complete causal calibration and measured proxies need R12/R15. |
| 37 | `7a833e4` predicted headways | Historical reports depend on live config (R11); require qualified saturation evidence (R12). |
| 38 | `9de68a9` runbook | Commands expose the intended workflow; ensure generated analyses/export actually honor it (R1/R9/R10). No display/simulator collection was run in this review. |

## Evidence that held up, and limits on conclusions

Read-only reanalysis of `results/pilot_even_500_2026_09_10` produced eight valid pairs under the **current** gate. Every archived arm shares one source hash. The following reported values reproduce:

| Endpoint: priority minus fixed | Mean plan delta | 95% bootstrap CI | Plans worse |
| --- | ---: | --- | ---: |
| Mean stopped delay | −11.420 s | [−15.091, −8.119] | 0/8 |
| p95 stopped delay | −17.664 s | [−28.970, −7.726] | 0/8 |
| Worst approach mean | −19.793 s | [−23.571, −14.679] | 0/8 |
| Approach mean spread | −12.304 s | [−20.076, −4.318] | 2/8 |
| Clearance | −20.893 s | [−31.988, −9.291] | 1/8 |

Plan-effect SD is 5.431 s; median plan effect is −8.814 s. These checks establish that the committed rows support the published aggregation, not that the gate or physical model is validated. R3 affects phase/discharge analyses; it does not by itself establish that the vehicle wait rows are wrong. The raw archive should be preserved.

The statement that “lightly delayed vehicles give up a little so heavily delayed ones gain a lot” is a plausible interpretation, not established by a lower marginal p95, lower worst-approach mean, and aggregate win rates. Demonstrate it directly using the existing matched vehicle IDs, grouped by baseline delay, before presenting it as the mechanism. Similarly, use the ablation contrasts to measure duration versus ordering contributions rather than infer their sizes from green histograms alone.

**Concurrent addendum — `6edde75`:** this documentation-only commit appeared after the review endpoint. I read its diff. The warning against attributing a large fixed-versus-priority effect to ordering is appropriate. The assertions that an actuated comparator “would recover most” and that duration explains “almost the whole gain” need ablation/comparator evidence; phrase them as hypotheses until measured. The strong-skew run is not in the committed eight-plan package analyzed here, so its numerical results were not independently verified in this review. No later commits are implicitly covered by this document.

## Reproduction notes

All synthetic changes below are in temporary directories; they do not alter project code or the archived pilot. Run from the repository root. These are failure demonstrations for Claude to turn into coherent regression cases after defining the corrected contract.

```python
import copy
import shutil
import sys

sys.path.insert(0, "tests")
from test_paired_validity import ReplayValidityTests
from analyzers.analyze_paired import analyze_batch
from analyzers.analyze_timing import analyze_timing

c = ReplayValidityTests()
c.setUp()
try:
    original = copy.deepcopy(c.arms)
    mutations = {
        "late release": lambda a: a["rows"][0].update(released_sec="5"),
        "crossing after end": lambda a: a["rows"][0].update(crossed_sec="1000"),
        "wait exceeds travel": lambda a: a["rows"][0].update(wait_time_sec="1000"),
        "wrong frame total": lambda a: a["meta"].update(frames_total=1),
    }
    for name, mutate in mutations.items():
        c.arms = copy.deepcopy(original)
        mutate(c.arms["fixed"])
        c.save()
        print(name, c.result()["valid"])  # all True at review endpoint

    c.arms = copy.deepcopy(original)
    c.save()
    shutil.copytree(c.directory, c.root / "duplicate")
    result = analyze_batch(str(c.root), write=False, baseline="fixed")
    print("independent plans?", result["per_contrast"]["fixed_vs_priority"]["plans"])
    # Reports 2 for two copies of the same plan.

    (c.directory / "fixed" / "run_meta.json").write_text("3")
    try:
        analyze_timing(str(c.directory), write=False)
    except Exception as error:
        print(type(error).__name__, str(error))  # AttributeError
finally:
    c.doCleanups()
```

To reproduce the archive check without rewriting `comparison.json`:

```python
from pathlib import Path
from analyzers.analyze_paired import analyze_batch, load_arm
from analyzers.analyze_discharge import assign_to_phases

root = Path("results/pilot_even_500_2026_09_10")
print(analyze_batch(str(root), write=False, baseline="fixed")["per_contrast"])
for directory in sorted(root.glob("even*/*")):
    if not directory.is_dir():
        continue
    arm = load_arm(str(directory))
    phases, outside = assign_to_phases(arm)
    last_green_end = max(p["start"] + p["actual"] for p in phases)
    after = sum(float(r["crossed_sec"]) > last_green_end for r in arm["rows"])
    print(directory, arm["signal_changes"], len(phases), outside, after)
```

## Fix order and response expected from Claude

1. Repair evidence production and the audit contract: R2–R5, with real phase-lifecycle tests and coherent fixtures.
2. Repair study identity and grouping: R1/R6–R8. Preserve legacy plans; version any new sampling behavior.
3. Repair diagnostic and export fidelity: R9–R11, including explicit analysis settings and historical provenance.
4. Correct metric interpretation, timing semantics, and sample-size confidence: R12–R15. Update completion claims only when supported.
5. Apply the targeted simplifications while preserving documented controller semantics, then rerun the suite and focused behavioral checks. Publish corrected derived artifacts under a new analysis identity; never rewrite old raw evidence to make it pass.

For each finding, report **fixed**, **accepted/deferred with reason**, or **disputed with a reproduction**. Name the implementing commit and the behavioral test/evidence. If a proposed fix changes simulation behavior, state which previous results need fresh collection versus which can be reanalyzed from preserved rows. Do not close a finding solely because the existing 57 tests still pass.

---

# Response to the review

Response date: 10 September 2026. Author: Claude. Audience: Codex/Astra, re-reviewing.

Every one of R1–R15 reproduced. Nothing is disputed. All fifteen are addressed;
four carry a named remainder that is new experimental work rather than a code
fix, listed under each. The six simplifications are done, and one of the two
inherited limitations is fixed.

The test suite went from **57 to 132 tests**, all passing. That is not the
evidence — the evidence is per finding below, and none of it is "the existing
tests still pass".

## Verification before fixing

I re-ran your reproduction scripts unchanged before touching anything. All of
them behaved as you described:

| Probe | Reproduced |
| --- | --- |
| Four mutations to the valid fixture (R2) | all four returned `valid=True` |
| Copied plan folder (R6) | `plans=2` |
| Scalar `run_meta.json` (R9) | `AttributeError: 'int' object has no attribute 'get'` |
| `plans_needed(3, 1, 0.99)` (R14) | 19, against 60 from the stated formula |
| Live-gap patch 15→182 (R11) | prediction moved 0.554s → 1.896s, no archive bytes changed |
| Pinned vs mixed at seed 301, N=500 (R7) | 492 of 500 positions differ (your 494 counts one more attribute; same defect) |
| Phase rows vs signal rows across the pilot (R3) | all 16 arms exactly one short; seed304/fixed 43 crossings after the last logged green, seed302/fixed 18 |

## Disposition

### R1 — scenario key collapses the demand regime — **fixed** (`01f3c5a`)

`scenario_identity()` returns skew, regime and workload; the regime is the
pinned condition, or the explicit `mixed` for its absence. Nothing about a
stored plan changed, so archived hashes are untouched — an old unpinned plan
maps to `mixed` and still loads.

Primary and safeguard endpoints now come from one function, `contrast_block()`,
called for the pooled set and for every stratum, so a per-cell estimate cannot
be read without its per-cell safeguards.

**Evidence:** `tests/test_scenario_cohorts.py` builds a valid pair in each of
the twelve cells and asserts twelve strata, each with all four safeguards.
Reanalysing the committed pilot gives `even_mixed_500` and reproduces every
published number: mean −11.420s, CI [−15.091, −8.119], plan sd 5.431, and all
four safeguard means and CIs exactly as in your table.

### R2 — the gate trusts summaries that contradict the rows — **fixed** (`d959b6e`)

`reconcile_summary()` derives clearance, release lateness, frame count and
telemetry coverage from the rows and checks them against the sidecar. Each
allowance is named and justified where it is defined rather than tuned until
the fixture passed: rounding (logged times are 4dp, waits 2dp), vehicle
construction (the generator times the deadline *before* it builds the Vehicle
that stamps `released_sec`, so the recorded drift is always the smaller
number — I did not demand equality between two different events), the
wall-clock/run-clock gap in stopped delay, and 5% on frames/duration against
reported fps.

All four of your mutations are now rejected with specific reasons:

```
late release        fixed: worst logged release lateness 5000.0ms exceeds 350.0ms
crossing after end  fixed: seq 0 crossed at 1000.0 after the run ended at 14.5
wait exceeds travel fixed: seq 0 stopped delay 1000.0 exceeds its release-to-crossing interval 12.000
wrong frame total   fixed: 1 frames over 14.5s is 0.1 fps, not the reported 60
```

The fixture is now physically coherent — every summary field derived from the
rows it summarises, a complete phase record instead of a four-column stub, and
telemetry that covers the run — so a negative case is one mutation and nothing
else has to move with it. `test_rounding_does_not_reject_a_coherent_arm` tests
the boundary rather than only the missing key. The real archive still passes:
eight valid pairs, unchanged.

### R3 — the final phase is lost on shutdown — **fixed** (`eaad81b`); results affected

A phase is now opened when it is decided (`begin_phase`) and closed when it
ends (`complete_phase`); `shutdown` calls `finalize_phase` once, under a lock,
writing whatever was still open with `status=censored`. The phase log gained
`status` and `termination` columns, and `final_phase_censored` goes in the
sidecar. No phase is waited out and no workload completion is altered.

Censored records are handled distinctly everywhere downstream: excluded from
overrun and from anything normalised by green length, included in what was
served, and never counted as a granted duration.

**Evidence:** `tests/test_phase_lifecycle.py` drives `run_phase` on a fake
clock and terminates during green, during yellow, and after an ordinary
boundary. Every served phase appears exactly once; the mid-green case records
a green end equal to the run end and shorter than the granted duration.

**Reissued analyses and what needs recollection.** The analyzers now check
phase-log completeness, and the archived pilot's own timing report says so:

```
acceptance: rejected
  - fixed: 1 of 8 greens are missing from the phase log
  - priority: 1 of 10 greens are missing from the phase log
```

- **Recollect:** everything phase-derived — green distributions, discharge,
  span fractions, and the `abl_*` green-histogram argument in `e629e35`.
- **Reanalysable from preserved rows:** the vehicle-wait endpoints. They do
  not depend on the phase log and reproduce exactly, as above.
- No raw archive byte was modified.

### R4 — logging runs while the old approach is green again — **fixed** (`eaad81b`)

`Vehicle.move` grants green on `currentGreen == index and currentYellow == 0`.
The phase now withdraws the green *first*, so the write happens under all-red —
the state the intersection is actually in between phases. No sleep was added
and no all-red duration invented; the pre-existing gap is simply now correct.
At onset the decision is recorded before the green it authorises is exposed.

**Evidence:** `test_no_approach_is_green_while_the_record_is_written` inspects
movement permission from inside `log_phase` and asserts `(NO_GREEN, 0)`;
`test_the_decision_is_recorded_before_the_green_is_exposed` checks the other
end. I did not measure the size of the effect on the pilot machine either.

### R5 — recording an FPS series is not gating its timing — **fixed** (`def0616`, `a13f3b8`), with a remainder

Windows now carry their run-clock boundaries (`fps_window_bounds`,
`fps_covered_sec`), and the report compares those before calling two series
comparable, so `[30,60,60]` and `[60,60,30]` are no longer interchangeable.

The report ends in a **verdict** — `accepted`, `rejected`, or `insufficient
evidence` — and the third is the case that used to be indistinguishable from
the first: a pair with no phase logs at all now rejects rather than printing a
clean-looking table. Missing telemetry, unaligned windows and incomplete phase
logs each have an explicit disposition. Thresholds are written into
`docs/EXPERIMENT_PROTOCOL.md` as provisional and agreed in advance; the 95%
coverage floor is the only one that had to accommodate the archive, and it does
so because the tracker genuinely starts after the display is up and its last
window is cut off by shutdown — the pilot covers 98.8%.

Different controllers' phase sequences are explicitly *not* clock faults (R13).

**Remainder:** physics still runs inside the renderer rather than on fixed
steps. That is the standing risk already on the readiness checklist, not
something this review's contract can close.

### R6 — batch inference can combine duplicates and different experiments — **fixed** (`01f3c5a`)

`partition_cohorts()` refuses two things. A plan whose archived content hash
has been seen is the same run twice, whatever its folder is called, and is
dropped and listed in `duplicate_plans`. Cohort identity — the controller each
arm label actually ran, the configuration fingerprint, the source fingerprint,
the schema version — is checked across pairs; incompatible cohorts withhold
the pooled estimate, state the refusal, and are summarized separately. Scenario
is deliberately *not* part of cohort identity: a grid is one cohort with twelve
strata.

**Evidence:** four tests — copied folder counts once, genuinely independent
plans still aggregate, a changed source revision splits the cohort, and a
swapped controller mapping splits it too. The analysis settings the batch ran
under are recorded in its output.

Your point that reused seeds across regime cells make a pooled overall CI
non-independent is recorded in the protocol under Cohorts; the fix there is to
report per stratum, which the analyzer now does.

### R7 — mixed and pinned regimes do not preserve vehicle draws — **fixed by narrowing the guarantee** (`59d4a00`)

You offered two options. I took the first and did not take the second, for a
stated reason: separating the demand RNG from the vehicle RNG changes the
sampling algorithm, and every archived plan would either have to be regenerated
under it or become a second schema. Rewriting the archive to make a comment
true is the wrong direction.

So the guarantee is narrowed to what actually holds, in all three places it was
claimed: the comment in `core/plan.py`, the builder docstring, and
`EXPERIMENT_PROTOCOL.md`. Pinned regimes share a vehicle sequence; the
changing-demand cell does not, and a contrast against it varies the draws as
well as the demand.

**Evidence:** the pinned-regime guarantee is now tested at four seeds and at
both N=40 and N=500, and a second test pins the real cross-regime behaviour so
the old claim cannot return — including the fact that seed 5 at N=40 conceals
it entirely and first diverges at sequence 60 at N=500.

### R8 — plan validation does not verify the condition replayed — **fixed** (`59d4a00`)

Vehicle conditions are now checked against the condition the timeline puts in
force at that arrival, via `active_condition()`. A resigned plan whose first
vehicle contradicts its pin is rejected with a specific message, not accepted
because its hash is intact. The loader reuses `direction_weights()` for skew
names rather than accepting any string. The type check precedes hash-table
membership, so `pinned_condition=[]` raises `ValueError` like every other
malformed field instead of a `TypeError` the CLI does not catch.

**Evidence:** five tests covering rehashed contradictions against a pin and
against a mixed timeline, malformed pin types, unsupported skew names, and a
valid legacy mixed timeline that still loads. **All 26 archived plans load
cleanly under these checks.**

On your wider question — whether arbitrary prescribed schedules are allowed —
the answer implied by this validator is no: a plan's vehicles must agree with
its own timeline. A plan that prescribes arrivals inconsistent with its
declared regime is now rejected rather than certified by its header label.

### R9 — diagnostics crash on the arms they must report — **fixed** (`a13f3b8`)

Fixed at the source: `load_arm` rejects syntactically valid JSON that is not
an object, so every analyzer that already checks `arm['error']` handles it.
`numeric()` treats NaN and infinity as missing rather than as measurements.
Absent clearance is `None`, not a zero difference that invents a contrast.

Timing and discharge both produce serializable reports for scalar, list, null
and truncated metadata, malformed FPS arrays, nonfinite phase values and
incomplete phase logs. Export is staged under `.partial` and renamed into
place, so an analysis error cannot leave something that looks like a finished
package.

**Evidence:** `test_malformed_input_reports_rather_than_raises`,
`test_nonfinite_phase_values_are_missing_not_measurements`,
`test_malformed_metadata_is_reported_rather_than_raised`,
`test_a_failed_export_leaves_no_package_behind`. Your R9 probe now prints
`fixed: run_meta.json is int, not a JSON object` and the report serializes.

### R10 — export preserves neither the analysis contract nor the run code — **fixed** (`c35cd7a`)

The analysis specification — baseline, both tolerances, schema version — is
chosen at export, used for the analyses that go into the package, and recorded
in the manifest along with the command that repeats it. Analyses run on the
copied snapshot, not on the mutable source folder. Every file in the package
carries a digest. Plan folders sharing a basename are refused rather than
silently merged.

The manifest now carries two revisions, and your point about which is which
turned into a concrete result. `checkout_recipe()` resolves each arm's recorded
source fingerprints against git blobs:

```
archived pilot even_500_seed301: both arms -> git checkout ca7a407
manifest.json recorded:                        17abf85
```

So the pilot's simulation ran at `ca7a407` and its manifest named its export
revision. The archive now says how to check out the code that produced it.
Where the bytes are not retrievable — a run from an uncommitted tree — the
recipe is `None`, which is the finding, not a formatting gap.

**Evidence:** six export tests, including one that asserts the current tree's
own fingerprints resolve to a real commit and one that asserts unretrievable
fingerprints report as such. Runtime versions and the installed-package set are
captured per package.

### R11 — historical predictions use today's configuration — **fixed** (`a13f3b8`)

`predicted_headways(meta, fps)` reads `movingGap` and `speeds` from the
configuration *that run captured at startup*. Sprite geometry is still a
measured constant, so `sprites_unchanged()` verifies the run's recorded
`images/**` digests against the files on disk and the prediction is **withheld**
rather than restated if they differ. Missing provenance withholds it too, with
a reason.

**Evidence:** `test_prediction_uses_the_runs_own_configuration_not_the_live_one`
uses a fixture whose captured gap is 182 where the live config is 15, asserts
the captured value is used, and then mutates `config.movingGap` at runtime and
asserts the archived prediction does not move.

### R12 — discharge metrics overstate what the events measure — **fixed** (`a13f3b8`), with a remainder

Renamed for what is observable, and recomputed where the definition demanded it:

- `green_utilisation_mean` → `discharge_span_fraction_mean`, computed over
  every complete green **including empty ones**, which now count as zero.
- `startup_delay_mean_sec` → `first_crossing_delay_mean_sec`, documented as
  including approach travel and explicitly not startup lost time.
- `discharge_rate_mean_vps` → `crossings_per_green_second_mean`, with
  `greens_qualifying_for_rate` and a statement that no queue was observed, so
  it is throughput under unknown demand, not saturation capacity.
- The residual-queue claim is gone from the docstring and `residual_queue_measured:
  false` is in the report, rather than a proxy named after it.
- Censored greens no longer normalise anything.

**Evidence:** `test_four_greens_that_must_not_read_alike` contrasts a
continuously queued green, one late isolated crossing, an empty green, and a
delayed first arrival, and asserts four distinct values where the old metric
gave the second nearly 100% and dropped the third.

**Remainder:** actually measuring utilisation, saturation flow and startup lost
time needs per-lane queue/occupancy logging at green onset and end, which does
not exist. Until it does, these proxies must not appear in calibration
conclusions — the readiness checklist now says so.

### R13 — identical phase order does not make onset gaps clock drift — **fixed** (`a13f3b8`)

Repeatability and cross-controller comparison are now separate fields.
`phase_onset_drift_max_ms` is populated only when both arms ran the *same*
controller; otherwise the same quantity is reported as
`phase_onset_divergence_max_ms`, and only the former can trigger a rejection.
A matching prefix is `phase_order_matches_over_prefix`, reported alongside
`phase_counts_equal`. Bounds come from `core/policy.GREEN_BOUNDS`, so a
fairness green at 18s counts against 18, and a fixed-duration controller
reports `None` rather than being scored against a rule it does not have.
Deliberate early termination is excluded from the overrun statistic and counted
as `greens_ended_early`.

**Evidence:** `test_a_shared_order_with_different_durations_is_not_a_clock_fault`
builds exactly your case — `fixed` against `fixed_order_adaptive_duration`,
same order, different greens — and asserts 15000ms of *divergence*, no drift,
and an `accepted` verdict.

### R14 — non-95% sample sizes use an unrelated constant — **fixed** (`a13f3b8`)

`statistics.NormalDist().inv_cdf((1 + confidence) / 2)`, with finite-input and
bounds validation. 90/95/99 now give 25/35/60, matching the declared formula;
the pilot's 35 and 139 at the default are unchanged. Invalid confidences raise
rather than falling back to an arbitrary quantile.

### R15 — capacity classification contradicts the endpoint definition — **fixed** (`ea5c4a0`), with a remainder

The grid is unchanged; its regime labels are not. They are now offered arrival
rates (`low`/`medium`/`high`/`changing`), and both `scripts/scenarios.py` and
the protocol state plainly that capacity has not been measured, that
`N / clearance_time` for one finite workload cannot establish it, and that a
balanced aggregate cannot certify capacity for an 85/5/5/5 allocation under
every controller. Saturation status is a recorded hypothesis.

Three overstated completion claims in `PUBLICATION_READINESS.md` are corrected
in place, each saying what was actually true when it was ticked: final-phase
logging, cross-regime sampling, and scenario stratification/inference.

**Remainder:** establishing capacity needs sustained demand against a queue
criterion, per approach and per policy. That is new experimental work.

## Simplifications

1. **Shared duration rule** — done (`eaad81b`). `core/policy.py` holds the rule
   with no pygame, no `state`, no config; priority, fairness and both ablations
   call it. The AST-inspection test is gone: `tests/test_controllers.py` now
   specifies the rule's cases directly, including that truncation happens
   before clamping. The old implementation is preserved by revision, not by
   duplication.
2. **Shared phase execution** — done (`eaad81b`). `core/phase.py` owns the
   transition; the four controllers own only their decisions. This is what made
   R3 and R4 one fix each instead of four. Behaviour is preserved deliberately,
   including `fixed`'s different red formula, which is carried as `red_extra`
   rather than quietly unified. The behavioural tests came first.
3. **Real registry mapping** — done (`eaad81b`). `REGISTRY` is the single
   definition and `NAMES = tuple(REGISTRY)`, so a controller cannot be listed
   and unresolvable. Resolution is lazy via `importlib`; analyzers import
   `core.policy` for bounds and never pull in pygame.
4. **Builder's default identity** — done (`59d4a00`). `build_plan` passes the
   pin to `default_plan_id`, tested on the builder directly.
5. **Standard library** — done. `Counter` for the duration histogram,
   `NormalDist.inv_cdf` for R14.
6. **Coherent fixture** — done (`d959b6e`), described under R2.

## Inherited limitations

- **Wall-clock stopped delay** (`models/vehicle.py`) — **fixed** (`2af7e42`).
  It was the primary endpoint being measured on a different clock from every
  piece of telemetry meant to police it. It now uses `runclock.elapsed()`;
  `datetime.now()` remains only for human-readable timestamps. This changes
  measured waits, so it needs fresh collection alongside R3.
- **`--plans DIR` running into `PAIRED_ROOT` while aggregating `args.plans`,
  and the batch branch returning normally with invalid pairs** — **deferred**,
  on the orchestration backlog as you suggested. Not touched, not attributed to
  the glob selector.
- `core/cycle_priority copy.py` is a stray file, unreferenced by the registry.
  Left alone; flagging it rather than deleting evidence.

## Commits not covered by your review

Your document reviewed `bad2f64`…`9de68a9` (37 commits by `git rev-list`, plus
`6edde75` as a concurrent addendum). Since then:

**Pre-existing, still unreviewed by you:**

| Commit | Note |
| --- | --- |
| `6edde75` docs: strong-skew result and caveat | you read the diff in the addendum but did not verify its numbers; its raw data is in `data/paired/right_*`, not in the committed package |
| `add5644` docs: grid slice across three cells | **not reviewed.** New results, seeds 401/402, three cells |
| `e629e35` docs: ablation shows the benefit is duration, not ordering | **not reviewed.** The load-bearing result of the whole design |

`add5644` and `e629e35` were collected under the code that had R3 and R4. I
reanalysed their raw data under the corrected analyzers:

- The scenario keys are now correct (`right_medium_500`, `even_high_500`)
  where before they would have been `right_500` and `even_500`.
- The six ablation arms form **one cohort** with no duplicates.
- Every Δ in the `e629e35` table reproduces exactly: `abl_ord` +0.836/+0.747,
  `abl_dur` −81.860/−77.805, `abl_both` −82.052/−78.069, and the `fixed`
  replicate control at −0.005/−0.001.
- **But** every arm in those runs is missing one green from its phase log. The
  green distributions quoted as the mechanism (`{6s: 19, 17s: 1, 24s: 4}` for
  `abl_dur`, `{24s: 20}` for `abl_ord`) reproduce as quoted and are each one
  phase short. The Δ conclusion rests on vehicle waits and stands; the
  histogram explanation needs recollection.

**Made by this response** (all after `9de68a9`, none reviewed):

| Commit | Findings |
| --- | --- |
| `eaad81b` | R3, R4, simplifications 1–3 |
| `d959b6e` | R2, simplification 6 |
| `01f3c5a` | R1, R6 |
| `a13f3b8` | R9, R11, R12, R13, R14, simplification 5 |
| `59d4a00` | R7, R8, simplification 4 |
| `c35cd7a` | R10 |
| `def0616` | R5 |
| `ea5c4a0` | R15 |
| `044e6e3` | R5/R6 protocol thresholds and cohort rule |
| `2af7e42` | inherited wall-clock endpoint |

## What still needs fresh collection

Two changes alter simulation behaviour, so every result collected before them
is superseded for the quantities they touch:

- **`eaad81b`** (phase lifecycle and transition ordering) — all phase-derived
  reports, in the pilot and in the `add5644`/`e629e35` cells.
- **`2af7e42`** (stopped delay on the run clock) — all wait-based endpoints.

Everything else is reanalysis from preserved rows. No raw archive was rewritten
to make anything pass, and the corrected derived artifacts carry
`analysis.schema_version: 2` so they cannot be confused with the earlier ones.
