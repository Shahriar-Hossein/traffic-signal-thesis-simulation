# Queue based traffic signal study

This branch studies **when queue based ordering and green allocation help** in a simplified four approach Pygame intersection. It is a new study based on `feature/modify-data-collection`; old experiments and paper material remain in that branch's history.

## Scope

There are two controllers: `fixed` and `priority`. The paired runner evaluates fixed at **12 s** and **24 s** green as two settings of the same controller. Both use **5 s yellow**. Priority orders the unserved approaches by weighted queue after each phase and selects a green in **6–24 s**. Every approach receives one phase per round. These settings differ from the submitted report's 12 s fixed and 4 s yellow, so old and new outcomes must not be combined.

The five environments are defined in [scripts/make_plan.py](scripts/make_plan.py): balanced moderate demand, one busy approach, two busy approaches, an exact high–low–high schedule, and sustained high offered load. Plans prescribe arrivals for a fixed duration, then the simulator runs until every planned vehicle crosses. `high` is an offered arrival rate, not a capacity finding.

## Run

Python 3 and Pygame are required. Generate development plans, then run the three arms sequentially against each plan:

```bash
python3 -B -m unittest discover -s tests
python3 scripts/make_plan.py --output-root data/study
python3 run_paired.py --plans data/study
```

For a short development probe, specify one environment and seed, then run its plan:

```bash
python3 scripts/make_plan.py --scenario balanced_moderate --seeds 301
python3 run_paired.py --plan data/study/balanced_moderate_seed301/plan.json
```

Each arm writes a vehicle log, phase log, signal log and metadata. `comparison.json` records the validity decision and paired effects. Batch analysis groups independent plans by environment and reports uncertainty from **plan level** differences. Vehicle rows are matched by plan sequence; they are not independent replicates. Negative delay or clearance difference means priority did better than the named fixed setting. Inspect per direction delay before interpreting an overall gain.

## Validation before study collection

1. Run the unit suite and a short development probe. Check priority's selected direction, selected 6–24 s green, and service of all four approaches using phase logs.
2. Require identical planned vehicle attributes and arrivals in every arm, complete crossing records, acceptable timing and frame rate evidence, and a valid `comparison.json`.
3. Only then collect several fresh independent plans in each environment. Keep failed runs and report ties or losses as observed.

The runner refuses reused arm folders. `data/` is ignored by Git; archive study evidence separately without editing raw plans or logs. The retained paired analyzer and timing checks enforce plan identity, crossing completeness, clock quality and source provenance. This model does not support a VANET performance or calibrated road capacity claim.
