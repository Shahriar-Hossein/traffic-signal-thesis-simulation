# Resume here: validation-first next actions

The project is in a verification phase, not a paper-production phase. Preserve
the uncommitted work and result archives. Do not launch a broad study merely
because the supporting runner, protocol or manuscript exists.

## 1. Verify the controller's observable rules first

Use short development-only probes with known queues and inspect phase/queue
telemetry. Establish each claim directly:

- The priority policy measures the intended queue weight and selects the
  intended next approach at each decision point.
- Its green calculation respects the configured floor and cap and reacts when
  queues differ; record when it instead sits on a bound.
- Its one-service-per-round behavior gives a bounded service gap, and its actual
  maximum/typical gap is measured rather than assumed.
- The fixed controller follows its declared rotation and duration, so it is a
  meaningful simple comparator.

Write a brief validation note with the scenario/seed, expected behavior,
observed telemetry and any mismatch. A passing aggregate delay alone does not
validate these rules.

## 2. Check representative environments at N=500

Use fresh development result roots and a deliberately small matrix: balanced
and strong skew; low, medium and high offered load; and one changing-demand
case. Re-run selected identical plan/controller pairs to check repeatability.

For every run, check plan hash and common arrivals, one crossing per planned
vehicle, phase/queue-observation coverage through the final phase, timing
acceptance, runtime/source identity, timeout/failure status and clearance.
Preserve failures and do not silently retry them away. Run arms sequentially;
avoid tests or other heavy work during collection.

## 3. Ask one mechanism question at a time

Compare `priority` with `fixed` first. Only add a single existing ablation or
comparator when it answers a concrete observation, such as whether ordering or
duration caused an effect, or whether skew produces an unacceptable service
gap. This phase is for understanding behavior, including no-effect and adverse
cases, not estimating a headline improvement.

## 4. Stop and decide after the validation note

The review must say what is demonstrated, what is uncertain and what design
change (if any) is justified. Only after that decision may a separate,
proportionate experimental plan be proposed. It must not reuse reserved seeds
or imply final evidence from development results.

## Hard hold

Do not work on `scripts/run_evaluation.py`, `scripts/make_paper_figures.py`,
the six-arm/936-run evaluation, fixed-timing tuning, collection-command
documentation, manuscript drafting, references, PDF/venue work, or image/figure
generation. They are retained but not integration targets during validation.
