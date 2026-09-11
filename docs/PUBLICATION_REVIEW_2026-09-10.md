# Publication readiness re-review — 10 September 2026

Reviewed by Codex against `d90a6bd340fa7b61dccc97566eb7706e8e82c395`, including Claude's response in `AGENT_HANDOFF.md:374` onward.

**Decision: not ready for definitive evaluation collection or conference submission.** Claude made substantial repairs, but “all fifteen addressed” is too strong: R5, R6 and the schedule portion of R8 remain incomplete. Fix the collection contract before spending days on evaluation runs.

This is a targeted re-review, not certification of every change. I read the handoff, protocol, readiness checklist and relevant implementation/tests; ran the suite; exercised temporary synthetic probes; reanalysed the committed pilot without writing; and checked the thesis PDF text. No simulator experiments were run. No implementation or raw results were changed. No conference has been identified, so venue-specific requirements were not assessed.

## What is verified

- `python3 -B -m unittest discover -s tests`: **132 tests, OK**. Explicit `-s tests` works; the warning about bare discovery in `CLAUDE.md` should not discourage this command.
- The shared phase executor, censored-phase lifecycle, monotonic stopped-delay clock, scenario identity, cohort partitioning and revised exporter are present. These are meaningful improvements. Passing the suite does not establish traffic-model validity or close the failures below.
- Read-only reanalysis of `results/pilot_even_500_2026_09_10`, baseline `fixed`, returns eight valid pairs under the current paired gate: mean stopped-delay difference **−11.420 s**, 95% bootstrap interval **[−15.091, −8.119]**. This confirms arithmetic reproducibility of the historical measurements, not eligibility as final publication evidence.
- Preserve that archive. Recollect final results under the frozen corrected implementation: phase transition behavior and the primary endpoint's clock have changed. Missing historical phases cannot be reconstructed from the existing phase rows.

## Remaining implementation blockers

### 1. R5: interval FPS failures still pass the timing verdict

Locations: `analyzers/analyze_timing.py`, `compare_timing()`, `boundaries_overlap()`, `acceptance()`.

Using the current paired test fixture, I supplied `[30,90,30,90]` to fixed and `[90,30,90,30]` to priority, preserving equal means and minima. The paired gate returned **valid**, the timing report measured **200% maximum window divergence**, and its verdict was **accepted**. No acceptance condition consumes the window-gap statistic.

Also, `boundaries_overlap()` returns `True` when boundaries are missing, contrary to its docstring and the protocol's insufficient-evidence rule. When boundaries exist it checks starts through `zip`, without validating full coverage, matching lengths, or interval ends. These omissions matter because physics still advances with rendering.

**Required:** specify and enforce interval comparability and FPS divergence; validate actual boundaries and coverage; treat absent evidence explicitly. Accommodate unequal run lengths through a justified common-interval comparison rather than requiring identical numbers of windows for controllers with different clearance times. Add regression cases for shifted stalls, missing boundaries, malformed/truncated boundaries and legitimate unequal durations. Decide thresholds in the protocol before collection.

### 2. R5: timing rejection does not control result eligibility

Locations: `analyzers/analyze_paired.py:analyze_pair()/analyze_batch()`, `run_paired.py:run_pair()`.

Deleting both phase files from the fixture gives **paired valid=True**, while timing says **rejected** for missing greens. `run_pair()` only prints the timing verdict and returns the original comparison. Batch aggregation selects on that comparison's `valid` field.

**Required:** distinguish a diagnostic calculation from a publication-eligible result. Propagate timing rejection/insufficient evidence to the driver, batch and exported eligibility status, with explicit reasons and failure counts. Historical vehicle endpoints may remain available for reanalysis, but must not silently enter the final evidence set. Regression-test the whole path, including command exit status. Resolve the already-deferred `--plans` output-root and batch exit-status issues before launching the grid.

### 3. R6: new plan IDs still turn repeated draws into independent replicates

Locations: `analyzers/analyze_paired.py:partition_cohorts()/analyze_batch()`.

I generated two fixtures with the same seed 41, even skew, high regime and workload, changing only the plan ID. Batch returned **two valid plans, no duplicates, plans=2**. The content hash contains naming metadata, so different hashes do not establish independent traffic draws.

The analyzer also still computes pooled bootstrap intervals in `per_contrast` across cells, although the protocol says reused seeds make the overall result descriptive. Documentation alone does not change these numerical outputs.

**Required:** define replicate identity independently of display names, using the generation scheme, seed/scenario and/or canonical traffic content. Separate reruns from new replicates. Report per-cell inference; remove unsupported pooled intervals or use an explicitly justified clustered design. Test renamed/regenerated same-seed plans as well as copied folders.

### 4. R8: demand labels are checked, but offered rates are not

Location: `core/plan.py:load_plan()`.

A high-pinned plan with three arrivals at **0, 100 and 200 seconds**, rehashed through `write_plan()`, loads successfully. Its vehicle condition labels agree with its timeline, but its offsets do not implement the declared high rate. Claude's statement that arbitrary inconsistent schedules are rejected is therefore not established.

**Required:** choose an explicit contract. Either validate the generator's offset/rate rules, including transitions, or support arbitrary schedules as a distinct mode and derive/report offered demand from the actual schedule. Do not certify a scenario's arrival rate from labels alone.

## Remaining research work, in dependency order

1. **Choose the claim and validate the model to support it.** For realistic traffic-efficiency claims, calibrate or independently cross-check following headways, startup behavior, geometry, turning/conflict handling and observation boundaries. Per-lane queue observations at green onset/end are needed before calling current proxies saturation flow, utilisation or startup lost time. Capacity remains unestablished. A deliberately abstract scheduling study can state narrower assumptions, but still needs robust comparative evidence. Do not turn the old unvalidated headway estimates into calibration targets without checking their measurement basis.
2. **Add competitive comparators.** Keep the two ablations, implement an actuated comparator and tune a fixed baseline on development data only. Fixed-24 alone cannot establish an advantage over existing responsive control. Strong-skew development results point toward duration allocation as the explanation; two seeds do not establish a general absence of ordering benefit.
3. **Revalidate timing and repeatability after the final code/model changes.** Run sequential identical-controller repeats at representative workloads, exercise end-of-run phase finalization, and check another machine if portability is claimed. Establish the new noise floor. If rendering speed changes outcomes materially, resolve the physics timing design before collecting final evidence.
4. **Freeze the protocol.** Resolve replication/precision per cell, controller tuning, all thresholds, failures/reruns, baseline/contrast direction, workload/horizon and seed allocation. The protocol is explicitly still a draft. Record all already-inspected development seeds, including 201 and 401/402 as applicable, rather than listing only 301–308. Verify that any claimed changing-demand experiment actually spans the intended transitions. Current skew is static; changing which approach is busiest requires an extension or a narrower claim.
5. **Collect fresh held-out evidence.** Use the reserved evaluation seeds only after freezing. Run arms sequentially, retain failed attempts, and summarize each scenario with independent-plan counts, mean stopped delay, tail/approach safeguards, clearance and mechanism measurements. Use cell-specific variability to justify replication; the balanced pilot's variance does not establish precision for every cell or comparator.
6. **Build the publication artifact.** Produce the configuration/scenario and results tables; cross-scenario effects with intervals; per-approach/tail results; and ablation/green-duration mechanism figures. Archive plans, exact commands, raw logs, configuration, retrievable run source, analysis version and figures. The exporter captures the analysis environment; record simulator runtime/dependencies at collection too, rather than assuming later installed packages describe historical runs.

## Remaining manuscript and submission work

- Write a conference manuscript from the frozen study. I found the thesis PDF, not a separate conference manuscript source. Its text still states 12-second fixed greens, 4-second yellow and time-limit termination, alongside count-based methodology. Preserve historical experiments as historical; do not rewrite their settings to match new runs.
- Position the contribution against relevant actuated and queue-responsive methods. Do not make a novelty claim solely for larger-queue-first service or demand-sized greens. A mechanistic, reproducible comparison could be the contribution, subject to final evidence.
- State the sensing and network boundary accurately: the current simulation does not establish packet-level VANET performance. A communication contribution needs corresponding modeled mechanisms and evaluation.
- Reconcile the readiness document's completion marks and historical assertions with this review. In particular, nominal capacity labels, green-utilisation wording and “frozen” design claims should not appear as current verified facts.
- Select the target conference and track, then check its actual scope, deadline, page limit, template, anonymity and artifact requirements. Acceptance probability cannot be inferred from the code review.

**Next concrete milestone:** close the four implementation blockers, then agree on model scope and competitive controls. Only after those choices should fresh validation and final collection begin. Plots and paper formatting come after a defensible evidence set.
