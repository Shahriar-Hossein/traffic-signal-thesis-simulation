# Current Codex checkpoint

Updated 14 September 2026: validation-first reset; writing and presentation are
on hard hold.

**Start with [CODEX_HANDOFF.md](CODEX_HANDOFF.md).** It indexes changes/rationale,
verified artifacts and exact next actions under `docs/codex_handoff/`.

- Immediate objective: establish, with small reproducible development studies,
  that the simulator and priority policy behave as specified across relevant
  demand situations. A conference paper is a possible later use of that
  evidence, not the current deliverable.
- Branch: `feature/modify-data-collection`; reviewed implementation, workflow,
  paper and validation changes are split into reviewable commits.

## Done

- [x] Defined the paper as a reproducible scheduling study in the simplified
  simulator, without calibrated-road, capacity or VANET-performance claims.
- [x] Implemented the six controller/comparator paths and sequential paired
  execution.
- [x] Repaired the major measurement, timing, provenance, plan-identity and
  publication-eligibility contracts identified in the review.
- [x] Separated development seeds from reserved evaluation seeds; no held-out
  seed has been used for study outcomes.
- [x] Implemented the development-only fixed-timing tuning workflow.
- [x] Drafted final-evaluation, manuscript and figure workflows. They are
  retained as future reference only and are not current work.
- [x] Passed the integrated suite: 183 tests OK, with one clean-tree-only check
  skipped.
- [x] Completed an accepted N=20 four-arm development validation and confirmed
  it by read-only reanalysis. Archive:
  `results/development_validation_2026_09_11_v2/`.
- [x] Preserved the first rejected validation attempt without rewriting its raw
  evidence. Archive: `results/development_validation_2026_09_11/`.
- [x] Drafted the manuscript methods, supervisor checklist and September
  delivery plan.

No long study is intentionally running now.

## Current validation plan

This is deliberately a learning and verification phase. Use development seeds,
fresh result roots and sequential runs only. Preserve raw results, including
failed runs; do not use reserved evaluation seeds.

1. **Controller-rule checks.** Run small, deterministic probes that verify the
   policy's observable rules: queue measurement, selected next approach,
   green-duration bounds/calculation, rotation/service guarantee, and fixed
   controller behavior. Inspect phase and queue telemetry, not just aggregate
   delay.
2. **Representative-environment checks.** At the actual 500-vehicle workload,
   repeat a deliberately small set of development plans spanning balanced and
   strongly skewed demand, low/medium/high offered load, and changing demand.
   Confirm plan identity, arrivals, crossings, timing coverage, queue
   observations and repeatability before interpreting controller differences.
3. **Mechanism checks.** Compare `priority` with the simple fixed baseline in
   the environments above. Add one ablation/comparator only when it answers a
   concrete question about *why* priority helped, failed, or changed fairness;
   do not automatically run all six arms or tune a best fixed controller.
4. **Review gate.** Summarize what the policy demonstrably does, where its
   effect is absent or adverse, what remains unvalidated, and whether the model
   is stable enough to justify a later experimental protocol. Only then decide
   whether a bounded comparative study is worthwhile and what it should test.

## Hard hold — not current work

- Paper/manuscript drafting, reference expansion, venue selection and PDF
  rendering.
- Figure, image or other presentation-asset generation, including synthetic
  paper figures.
- The held-out six-arm evaluation, the proposed 936-run grid, protocol freeze,
  and fixed-timing tuning/selection.
- Completing infrastructure whose only purpose is final collection or paper
  presentation (`run_evaluation.py`, paper plotting, collection commands),
  unless it becomes necessary for a specific validation check.

## Next action

Read [the validation-first next steps](codex_handoff/next_steps.md). Start with
controller-rule probes, then run only the small representative N=500
development validation set. Do not start tuning, held-out collection, writing
or visual work.
