# Traffic-signal working rules

- This branch is a plan-only paired study: fixed 12 s, fixed 24 s, and priority use the same scheduled traffic plan.
- Keep `docs/Thesis_Report_5-9-26_update.pdf` as historical thesis context; its results are separate from this study.

- Research data is the product. A completed simulation is not automatically valid evidence.
- Use `run_paired.py` for sequential comparisons. Do not run simulator arms concurrently.
- Keep raw plans and logs immutable. Use fresh output roots for probes and `write=False` for historical reanalysis.
- The independent replicate is a traffic plan, not a vehicle or rerun. Infer per environment; reused seeds across environments do not add independent overall replicates.
- Validate selected direction, 6–24 s priority green, four approach service, identical arrivals, complete crossings, timing and frame rate before collection.
- Report stopped delay, clearance time, and each approach's delay. Show ties and losses. Do not call offered rate or clearance proxies capacity.
- A simulator, model or clock change requires fresh validation and new evidence. Old results cannot be relabeled.
- Run `python3 -B -m unittest discover -s tests` and check the test count and exit code.
- Update `docs/CODEX_WORKING_STATE.md` at milestones with the next actionable step.
