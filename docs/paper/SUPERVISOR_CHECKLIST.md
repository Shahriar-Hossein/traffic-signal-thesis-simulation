# Supervisor checklist

**Purpose:** make the six-arm scheduling study ready for supervisor review and
for a later venue decision. This checklist makes no venue-specific format or
acceptance promise. The paper reports no final result until fresh evaluation is
collected under a frozen protocol.

## Review this draft

- [ ] Approve the claim boundary: a reproducible scheduling comparison in a
  simplified simulator, with no calibrated road, capacity, field-detector,
  network, or packet-level VANET claim.
- [ ] Confirm the six arms: `fixed` (24 s), `priority`,
  `fixed_order_adaptive_duration`, `adaptive_order_fixed_duration`,
  `actuated`, and development-only `fixed_tuned`.
- [ ] Confirm that the priority demand rule is described as
  `W = sum(1 / configured speed)` over uncrossed vehicles, including
  moving/offscreen vehicles, with recounting after each served approach and a
  6–24 s green fixed at onset.
- [ ] Confirm that “changing demand” means changing total offered arrivals;
  directional skew is static within a plan.
- [ ] Confirm the primary endpoint and safeguards: plan mean stopped delay,
  p95 stopped delay, worst-served approach and service gap; report travel and
  last-crossing clearance separately.
- [ ] Confirm the literature positioning and references, especially the
  distinction between the simple local actuated comparator, queue/pressure
  control, and VANET control.

## Freeze before evaluation

- [ ] Complete timing and observation-boundary validation, including FPS and
  release timing, phase-log completeness, turning/merge behavior, vehicle
  conservation, and the effect of frame-dependent physics.
- [ ] Define and record the `fixed_tuned` selection procedure using development
  plans only; freeze its timing table before using evaluation seeds.
- [ ] Decide the target number of independent plans in each of the 12 cells,
  using development variability and a stated confidence-interval precision
  target. Record the actual replication count once chosen.
- [ ] Freeze seed allocation and keep evaluation seeds **9001–9020** untouched
  until the protocol, controller settings, thresholds, retry rules, and
  analysis version are frozen. Record inspected development seeds, including
  201, 301–308, and 401/402 as applicable.
- [ ] Freeze failure handling: run arms sequentially, retain every failed or
  timed-out attempt, report failures by cell and arm, and never convert a
  retry or renamed copy into an independent replicate.
- [ ] Freeze the analysis contract: plan identity/content hashes, per-cell
  inference, paired mean differences, 95% percentile bootstrap intervals, and
  descriptive-only pooled summaries.

## Collect and audit

- [ ] Run all six arms against each identical finite 500-vehicle plan; preserve
  plans, raw logs, commands, configuration, source/dependency fingerprints,
  runtime telemetry, and analysis metadata.
- [ ] Apply the paired validity gate before an effect enters a table or figure;
  count and explain invalid pairs rather than silently excluding them.
- [ ] Verify that clearance is `last_crossing_sec` and that the post-crossing
  display drain is excluded. Do not call finite-workload completion a capacity
  estimate.
- [ ] Check green-duration distributions and bound frequencies for mechanism
  interpretation, and ensure phase logs cover the final censored phase.

## Complete the paper package

- [ ] Replace the pending Results section only with fresh, valid held-out
  evidence. Include independent-plan counts, failures, absolute values,
  per-cell effects and intervals, safeguards, clearance, travel, and mechanism
  summaries.
- [ ] Add the planned configuration/scenario and results tables plus delay,
  approach-safeguard, and mechanism figures, with commands and source data
  archived outside the ignored working-data tree.
- [ ] Recheck every conclusion against uncertainty, failure counts, and the
  model limitations. Keep historical pilots clearly marked development-only;
  do not relabel them as final evidence.
- [ ] Obtain supervisor approval of the scientific scope and evidence package;
  select a conference and apply its format only afterward.
