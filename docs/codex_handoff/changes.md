# What changed and why

See [handoff index](../CODEX_HANDOFF.md) for scope and current completion status.

## Review that motivated implementation

Claude's response said all fifteen prior findings were addressed. A targeted
re-review reproduced four remaining collection problems despite 132 passing tests:

| Failure | Why it matters |
| --- | --- |
| Shifted FPS stalls passed both paired validity and timing acceptance | Equal averages/minima do not mean comparable frame-dependent physics |
| Missing phases produced a timing rejection but a valid paired effect | Rejection must control collection eligibility, not merely be printed |
| The same seed under different plan IDs counted twice | Naming metadata is not an independent experimental replicate |
| A high-demand plan with offsets 0/100/200 seconds loaded after rehashing | Matching labels do not establish the actual offered arrival rate |

Evidence is preserved in [PUBLICATION_REVIEW_2026-09-10.md](../PUBLICATION_REVIEW_2026-09-10.md).

## Implemented measurement and collection changes

| Files | Change and reason |
| --- | --- |
| `analyzers/timing_contract.py` | Validates actual FPS interval boundaries, coverage, finite values and overlap; compares the common elapsed horizon when runs finish at different times |
| `analyzers/analyze_timing.py` | Enforces interval FPS divergence, handles missing evidence explicitly, checks phase transitions against run duration, records threshold settings, supports explicit baseline and returns a failing CLI status when timing is not accepted |
| `analyzers/analyze_paired.py` | Analysis schema 3; separates raw measurement validity, timing acceptance and publication eligibility; withholds effects for ineligible pairs; checks runtime provenance and persisted driver failures |
| Same analyzer, grouping sections | Uses canonical traffic and scenario/seed identity to identify reruns; preserves old plan hashes; withholds cross-scenario inferential intervals; retains per-cell safeguards and cohort breakdowns |
| `core/plan.py` | Enforces the generated regular-arrival/timeline contract, including repeated pinned timeline events and missing final events; tolerances follow six-decimal serialization |
| `core/provenance.py` | Captures Python/pygame/platform/SDL runtime, executable and argv at startup; separates comparison identity from arm-specific invocation paths |
| `run_paired.py`, `main.py`, `state.py`, `utils/logger.py` | Plumbs explicit output roots; preflights sweeps; selects exact plan IDs; records process failures so reanalysis cannot silently recover them; removes effects on failure; explicit baseline support was added by the interrupted evaluation agent and needs its own regression coverage |
| `scripts/export_results.py` | Passes baseline and FPS tolerance into timing analysis as well as paired analysis |
| `main.py:FpsTracker` | Retains final partial telemetry; after a real failure, corrected its endpoint to the last observed frame rather than the later shutdown time |

Old raw archives were not rewritten. Fresh validation outputs live in separate
new result roots. Runtime provenance is not inferred from packages installed
later during export.

## Comparators and observations

- `core/cycle_actuated.py`, `core/detectors.py`: fixed rotation, minimum 6 s,
  maximum 24 s, gap-out after two elapsed sampled-empty seconds. A detector uses
  the vehicle front within 100 px upstream of the stop line, sampled once per
  controller second. This is a defined model comparator, not calibrated hardware.
- `core/fixed_timing.py`, `core/cycle_tuned_fixed.py`: validated scenario-specific
  four-approach green tables, no missing-cell fallback, development-seed checks,
  and `fixed_tuned` execution. The validation table is hand-specified; **actual
  development tuning has not happened**.
- `core/controllers.py`, `core/policy.py`: registers the two comparators and their
  bounds while retaining the original proposal and two ablations.
- `core/observations.py`, `core/phase.py`, `utils/logger.py`: lane-level uncrossed,
  stopped and detector-zone counts at green onset/end/censoring. A yellow-time
  shutdown now retains the true green-end snapshot. Yellow indication remains
  on the served approach, while movement permission is withdrawn.
- These snapshots do not establish continuous occupancy, saturation flow,
  startup lost time or utilisation. Do not relabel them as those quantities.

## Study automation

`scripts/tune_fixed.py` supports development-only preparation, sequential run/resume
and selection. Three candidates are predeclared: uniform 12 s, uniform 24 s and
96 s proportional green with approach bounds 6–60 s. Strong skew gives
60/12/12/12. It requires complete scenario/seed coverage, selects from raw waits,
checks recorded candidate settings, preserves a simulator source snapshot and
validates source/runtime/input digests. Default development seeds are 301/302.
It has focused tests but has not executed an actual tuning study.

Two late agents hit the usage limit:

- `scripts/run_evaluation.py`: preparation, guarded resume, explicit baseline,
  arm-order rotation and per-cell analysis were drafted. Dedicated promised
  `tests/test_evaluation_manifest.py` and collection-command document were not
  created. Treat this script as requiring review and tests.
- `scripts/make_paper_figures.py` and `tests/test_paper_figures.py`: CSV/plot support
  was drafted; data-path tests run, but actual rendering has not been tested.
  Matplotlib is not installed. Interfaces do not yet fully agree with evaluation
  output; see next steps.

## Documents and reusable guidance

- `docs/paper/manuscript.md`: roughly 1,960-word venue-neutral methods/design
  draft, with a clearly pending results section and no invented final effects.
- `docs/paper/SUPERVISOR_CHECKLIST.md`, `SEPTEMBER_DELIVERY_PLAN.md`: remaining
  submission work and planning windows, not promises of completed milestones.
- `docs/RELATED_WORK_NOTES.md`: FHWA timing guidance, Varaiya max-pressure and
  Pandit et al. VANET control; explains what this simulator does not evaluate.
- `docs/EXPERIMENT_PROTOCOL.md`: updated claim scope, six arms, provisional
  thresholds and development selection plan. **Still not frozen.**
- `docs/PUBLICATION_READINESS.md`, `docs/AGENT_HANDOFF.md`: current-scope notes
  added without replacing the historical record.
- `AGENTS.md`: project rules, cheap startup path, agent ownership, test/collection
  separation and evidence invariants.
- `/home/shahriar/.codex/AGENTS.md`: personal Codex preferences adapted from
  `/home/shahriar/.claude/CLAUDE.md`, without unsupported billing claims.
- `/home/shahriar/.codex/skills/efficient-research-code/SKILL.md`: installed and
  validated reusable workflow; now discoverable in the session skill catalog.

## Delegation and lessons

Luna handled arrival validation, runtime capture, fixed-plan support, lane
snapshots and document completion. Sol handled replicate identity, driver
plumbing, tuning workflow and the interrupted evaluation script. Terra handled
the actuated comparator and primary-source positioning. The lead handled the
validity design, integration, real runs and review of agent outputs.

Useful corrections found during integration:

1. N=40 pinned/high plans never reach a 120 s transition; use N=500 and multiple
   regimes when testing periodic behavior.
2. `write_plan()` does not populate the caller's in-memory header hash. Reload
   the written plan when recording its identity.
3. Simultaneously clamping both upper and lower proportional shares can leave
   unallocated green; the bounded allocator must redistribute remaining budget.
4. Phase observations must be stored at the actual green end, not held until
   yellow completion, or shutdown substitutes the wrong snapshot.
5. Shutdown's final sleep is not another rendered frame. FPS interval boundaries
   must describe observed frames, not the later exit timestamp.

Some agents ran broader tests than requested. Future briefs should explicitly
limit them to their owned tests, leaving integrated verification to the lead.
Do not run tests or other heavy local work while collecting simulator arms.
