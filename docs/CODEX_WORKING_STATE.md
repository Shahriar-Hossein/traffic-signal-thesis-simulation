# Current Codex checkpoint

Updated 12 September 2026 with the current done/remaining checklist.

**Start with [CODEX_HANDOFF.md](CODEX_HANDOFF.md).** It indexes changes/rationale,
verified artifacts and exact next actions under `docs/codex_handoff/`.

- Objective: supervisor-ready conference paper within September; simplified
  simulator scheduling study, venue after supervisor review.
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
- [x] Drafted the final-evaluation and paper-figure workflows. These remain
  integration work, not verified final deliverables.
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

## Remaining, in order

- [ ] Finish and test the evaluation runner, including workflow dependency
  hashes, exact selected-plan handling, arm-order rotation, resume behavior and
  explicit failure accounting.
- [ ] Finish the plotting interface and render synthetic validation figures,
  including safeguard intervals and valid interval/error-bar handling.
- [ ] Add verified collection commands and run the complete test suite once
  after integration.
- [ ] Run representative N=500 repeatability and telemetry validation using
  fresh development roots.
- [ ] Run development-only fixed-timing tuning: 72 paired comparisons and 144
  sequential simulator arms.
- [ ] Select and freeze the `fixed_tuned` timing table from complete development
  coverage.
- [ ] Decide the independent-plan count and precision target, then freeze the
  protocol, seeds, thresholds, arm ordering, retry/failure policy and analysis
  version.
- [ ] Collect the held-out six-arm evaluation. The current planning target is 13
  plans per cell across 12 cells: 936 sequential simulator runs.
- [ ] Audit validity and failures, then produce per-scenario estimates,
  intervals, safeguards, clearance and mechanism summaries.
- [ ] Generate the final tables and figures and replace the manuscript's pending
  Results section only with eligible held-out evidence.
- [ ] Recheck references, conclusions, limitations and the reproducibility
  package; obtain author names and affiliations.
- [ ] Render and visually inspect the supervisor-ready paper, obtain supervisor
  review, and only then select and apply a conference format.

## Next action

Read [the detailed next steps](codex_handoff/next_steps.md), finish evaluation
and plotting integration, then validate the full N=500 path before starting the
tuning study.
