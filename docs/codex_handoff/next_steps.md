# Resume here: next actions

Read the [handoff index](../CODEX_HANDOFF.md), then inspect only the relevant
files. Preserve the uncommitted work and both new result archives.

## 1. Finish interrupted integration before another long run

Two agents stopped at a usage limit. Do not assume their files are finished
because they have a CLI or because existing tests pass.

**Evaluation runner (`scripts/run_evaluation.py`):**

- Review source/runtime/protocol/table freeze checks and exact selected-plan
  handling. `WORKFLOW_FILES` currently omits `analyzers/timing_contract.py`, which
  contains acceptance logic; include transitive workflow dependencies.
- Add the promised `tests/test_evaluation_manifest.py`. Test refused preparation
  before protocol freeze, complete plan coverage, arm-order rotation with fixed
  baseline, resume of valid completed pairs, rejection of incomplete/failed
  attempts, provenance drift and exact per-cell analysis.
- Review/test the late `run_paired.py --baseline` addition. It separates arm
  execution order from contrast direction; existing tests did not specifically
  exercise the new counterbalanced path.
- Check how legitimate failed evaluation arms are reported. Current analysis
  refuses any invalid pair; the final study still needs explicit failure counts
  and an honest disposition, not discarded failures or endless retries.
- Add the promised `docs/paper/COLLECTION_COMMANDS.md` once commands are verified.

**Plotting (`scripts/make_paper_figures.py`):**

- Actual rendering is untested and matplotlib is absent. Install only a needed
  analysis dependency in a deliberate location, record its version, and render
  synthetic validation figures before using real study outputs.
- The plot reader requires `study_stage=evaluation`, but the evaluation runner
  does not currently add that tag to its per-scenario reports. Integrate these
  interfaces without falsely relabeling development data.
- Safeguard bars currently omit their intervals; final safeguards need uncertainty
  beside their estimates. Avoid overwide/unreadable multi-scenario charts.
- The primary errorbar code assumes the point estimate is inside its interval;
  review handling of a valid interval that does not contain the point, rather
  than manufacturing a negative errorbar length or altering the interval.
- Validate cohort selection against the analyzer's actual nested schema.
  Current tests mainly cover data extraction, not rendering or the whole pipeline.

Keep agent tests scoped. Once integrated, run the complete suite once and verify
the count/exit code. No simulator arms are intentionally still running now.

## 2. Validate at the actual workload and tune fixed timing

The corrected N=20 smoke test passed. Next validate N=500 with repeated identical
controllers and representative cells. Check full telemetry coverage, final
phases, observation timestamps, runtime/source equality and effect noise. Use
fresh development roots; never overwrite or silently retry an invalid attempt.

`scripts/tune_fixed.py` is implemented and tested but has not launched a study.
Default design: 12 cells × two development seeds × three candidate pairs =
72 sequential fixed-versus-fixed_tuned pairs, 144 simulator arms.

After integration, an intended preparation command is:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 scripts/tune_fixed.py prepare \
  results/fixed_tuning_development_2026_09_11 --seeds 301 302 --count 500 --timeout 3000
```

That destination does **not** exist at handoff. Preparation generates development
inputs and freezes source/runtime. Do not edit frozen simulator/workflow files
afterward and expect collection to resume unchanged.

```bash
# Explicit execution, initially bounded for end-to-end validation:
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 scripts/tune_fixed.py run \
  results/fixed_tuning_development_2026_09_11 --max-pairs 1

# Later continue the same frozen study, then select only after full coverage:
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 scripts/tune_fixed.py run \
  results/fixed_tuning_development_2026_09_11
python3 scripts/tune_fixed.py select results/fixed_tuning_development_2026_09_11
```

Use the same display/runtime settings during prepare and run; those settings are
part of the frozen identity. The first low-rate N=500 pair alone needs over
33 minutes of release time across its two arms. Measure and budget total runtime;
do not mistake the short smoke check for a study runtime estimate.

The candidate search is intentionally bounded, not globally optimal fixed
timing. Require every candidate's planned development coverage, preserve failures
and select from the actual recorded candidate settings and raw waits.

## 3. Freeze the evaluation design, then collect

- The current protocol is still a draft. The planning target is 13 independent
  plans per cell, seeds 9001–9013, six arms, 12 cells: **936 simulator runs**.
  This is a proposed compute/precision target, not a guaranteed CI width.
- Finalize the fixed-table selection, replication count, primary contrasts,
  safeguards, threshold settings, arm-order counterbalancing and failure policy
  before looking at held-out outcomes.
- Evaluation preparation currently requires an explicit `Status: frozen` line
  and a nonempty freeze note plus selected-table evidence. Do not add the marker
  merely to bypass the guard.
- Capture a retrievable source snapshot and actual run environment, not only a
  Git revision from a dirty tree or a later analysis environment.
- Run sequentially on the same machine; do not run tests or other heavy local
  work at the same time. Report per scenario, without pooled cross-cell CIs.

## 4. Complete the supervisor package

- Replace the manuscript's pending-results section with validated final tables,
  effects/intervals, tail and approach safeguards, clearance and mechanism plots.
- Interpret the two ablations against both competitive comparators. Do not
  conclude that ordering helps, or never helps, from the old two-seed examples.
- Check cited primary sources and strengthen positioning as needed; current
  notes are a bounded starting set, not an exhaustive novelty review.
- Obtain author names/affiliations and intended supervisor authorship before
  producing the final manuscript. These details have not been requested yet.
- Render a readable supervisor artifact and check it visually; no final PDF
  pipeline or venue template has been set up.
- Preserve the university thesis PDF's historical experiment settings. Its
  12 s/4 s/time-limit descriptions cannot be relabeled as the new 24 s/5 s/count
  study. An editable thesis source was not found in the initial inventory.
- Aim for a complete draft around 25–27 September and reserve the remainder for
  supervisor corrections. The September delivery plan is a planning aid, not a
  claim that collection or submission is already complete.

## Rules to preserve

The user wants continued autonomous work, bounded lower-cost delegation, compact
progress updates and durable checkpoints. Use Luna for genuinely small tasks and
Sol/Terra for isolated implementation; keep scientific decisions and integration
with the lead. Do not launch more agents while a usage limit prevents their work.
Do not commit or submit externally without actual user authorization.

When the work is truly complete, say so. Until then, distinguish implemented
software, development validation, final evidence and supervisor-ready writing.
