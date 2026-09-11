# Current Codex checkpoint

Updated 11 September 2026 after review and commit preparation.

**Start with [CODEX_HANDOFF.md](CODEX_HANDOFF.md).** It indexes changes/rationale,
verified artifacts and exact next actions under `docs/codex_handoff/`.

- Objective: supervisor-ready conference paper within September; simplified
  simulator scheduling study, venue after supervisor review.
- Branch: `feature/modify-data-collection`; reviewed implementation, workflow,
  paper and validation changes are split into reviewable commits.
- Current integrated suite: 183 tests OK, one clean-tree-only check skipped.
- Fresh corrected N=20 four-arm development validation passed; current read-only
  reanalysis agrees. Archive: `results/development_validation_2026_09_11_v2/`.
- First rejected attempt preserved: `results/development_validation_2026_09_11/`.
- Both validation attempts finished; no long study intentionally left running.
- Tuning and final evaluation have not started. Protocol not frozen; evaluation
  seeds unused for study outcomes. Manuscript results remain pending.
- Evaluation and plotting scripts are committed as explicit drafts. Finish their
  missing evaluation tests, workflow hashes and output interfaces before launch.
- Next: read `codex_handoff/next_steps.md`, finish integration, validate N=500,
  then perform development tuning and freeze the final evaluation design.
