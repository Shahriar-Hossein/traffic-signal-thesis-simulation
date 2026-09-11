# Verification and preserved artifacts

## Tests

At the user-requested handoff, after the real simulator finished:

```bash
python3 -B -m unittest discover -s tests
git diff --check
```

**183 tests ran; OK, one skipped.** `git diff --check` produced no errors.
The skip is the export test requiring current fingerprints to resolve to a
clean Git commit; the working tree is deliberately uncommitted. This does not
verify the newly drafted evaluation runner or matplotlib rendering.

The complete test console is [tests.log](tests.log). Earlier milestones were
132 tests at review, then 172/177 during integration; use 183 for this checkpoint.
Do not treat a bare unittest discovery that finds zero tests as a pass.

## First fresh attempt: rejected and retained

Root: `results/development_validation_2026_09_11/`

- N=20, seed 301, balanced/high demand.
- Sequential arms: `fixed_a=fixed`, `fixed_b=fixed`, `actuated`, `fixed_tuned`.
- Fixed-plan table: 12/12/12/12, explicitly **validation-only, not tuned**.
- All arms completed, but the comparison was rejected for FPS divergence.
- The fixed-plan arm's last window was about 0.1113 s at 53.89 FPS. It included
  the sleep after the last rendered frame; no next frame occurred before exit.
  That biased the short-window rate and caused 13.58% interval divergence.
- Corrected the measurement endpoint; did not loosen the 5% threshold or rewrite
  this run's raw logs. Its console, inputs, logs and source snapshot are retained.

## Corrected fresh attempt: accepted

Root: `results/development_validation_2026_09_11_v2/`

Plan folder: `runs/even_high_20_seed301/`

The same four-arm development check was repeated with corrected telemetry.
All 20 vehicles crossed in each arm. The driver reported **valid pair** and
timing **accepted**. Current read-only reanalysis at handoff also passes.

| Observation | Result |
| --- | --- |
| Repeated fixed mean stopped-delay difference | −0.002 s |
| Repeated fixed clearance difference | about −0.005 s |
| Repeated fixed maximum phase-onset drift | 3.5 ms |
| Final phase records | all four arms account for all four onsets; final phase censored |
| Repeated fixed p95 interval FPS divergence | 0.59% |
| Actuated / fixed-plan p95 interval divergence against fixed_a | 0.63% / 0.61% |

This validates the exercised execution/logging path. **It is one small
development plan, not a replicated publication experiment or a new N=500 noise
floor.** Do not transplant its controller effect sizes into the paper.

Exact invocation used for the corrected attempt:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python3 -B -u run_paired.py \
  --seed 301 --count 20 --uneven-mode even --condition high \
  --arms fixed_a=fixed fixed_b=fixed actuated fixed_tuned \
  --fixed-timing-plan results/development_validation_2026_09_11_v2/validation_timing.json \
  --output-root results/development_validation_2026_09_11_v2/runs --timeout 300
```

Do not rerun into that existing root: the driver correctly refuses overwrites.
Use a new named development root for further collection.

Each attempt includes `source/`, `source_manifest.json`, `console.log`, the timing
table and raw/derived run files, about 8.2 MB per attempt. Source snapshots preserve
the code used even though no new Git commit was authorized. Later changes to
analysis/driver files are not retroactively part of those snapshots.

## Other verification

- Arrival-validation development probes loaded all 26 existing plan files across
  historical `data/paired` and the committed pilot without rewriting hashes.
- Historical pilot arithmetic was reproduced during review: eight plan means,
  −11.420 s, CI [−15.091, −8.119]. That predates the new eligibility requirements;
  it remains historical development evidence and should not be called a currently
  eligible final dataset.
- Runtime snapshot, comparator geometry, arrival boundaries, duplicate plans,
  interval telemetry, invalid export paths and driver failure behavior have
  targeted regression coverage.
- The installed research skill passed `quick_validate.py`.
- No dependencies were installed for plots. `matplotlib`, `reportlab` and `docx`
  were absent; `pdflatex`, `pandoc` and `typst` were not found during inspection.

No final evaluation, N=500 new repeatability study, fixed-baseline selection,
paper plot rendering, PDF compilation, commit, push or supervisor submission
was performed.
