# Codex handoff — 11 September 2026

Start here when resuming. This records the work across the interrupted sessions,
why it was done, what was verified, and the next actions. The user requested
this handoff after two sessions reached usage limits.

## Objective and decisions

- Deliver a **supervisor-ready conference-paper draft within September 2026**.
  Supervisor review comes before venue selection. The report submission gates
  the user's degree certificate; they need next month for applications and IELTS.
- The user chose **a reproducible scheduling study in the simplified simulator**.
  Do not expand the immediate task into real-road calibration or claim realistic
  traffic efficiency, network capacity, or packet-level VANET performance.
- The user authorized bounded lower-cost delegation and reusable Codex guidance.
  They did not request a commit, push, or external submission.

## Status at handoff

**The paper is not finished or ready for supervisor submission.** The measurement
pipeline and comparator support are substantially improved, a real development
validation passed, and a manuscript draft exists. Fixed-baseline tuning,
full-workload validation, held-out evaluation, final plots and results remain.

- Latest suite: **183 tests, OK, one skipped**, checked at this handoff.
- Corrected real validation: N=20, seed 301, even/high, four sequential arms;
  **valid pair and accepted timing**, also confirmed by current read-only reanalysis.
- No N=500 tuning study or final evaluation was launched. Reserved evaluation
  seeds have not been used for study outcomes.
- The final evaluation/plotting agents hit a usage limit. Their files exist,
  but are **unfinished integration work**, not verified deliverables.
- All project changes are **uncommitted**. HEAD remains
  `d90a6bd340fa7b61dccc97566eb7706e8e82c395`. Preserve the working tree.
- Both development validation attempts finished. No long study is intentionally
  left running at this checkpoint.

## Read only what you need

1. [Changes and rationale](codex_handoff/changes.md) — implementation, documents,
   delegation and instruction files.
2. [Verification and artifacts](codex_handoff/validation.md) — tests, rejected
   first run, successful corrected run and exact artifact locations.
3. [Next actions and known gaps](codex_handoff/next_steps.md) — ordered continuation,
   commands, incomplete agent work and decisions still needed.

The working manuscript is [here](paper/manuscript.md). Also see the
[supervisor checklist](paper/SUPERVISOR_CHECKLIST.md),
[September delivery plan](paper/SEPTEMBER_DELIVERY_PLAN.md), and
[current experiment protocol](EXPERIMENT_PROTOCOL.md).

`AGENT_HANDOFF.md` contains the earlier Codex review and Claude's reply. It is
historical context, not the current task list. Do not reread all of it to resume.
