# Current checkpoint

Branch: `feature/modify-data-collection-simplified`, based exactly on `feature/modify-data-collection` at `ee4fcbc` before these uncommitted edits.

The working tree now keeps only the paired runner, fixed and priority controllers, their simulator dependencies, paired delay/clearance/timing analysis, required sprites, and focused tests. Old tracked results and paper tooling are removed from this branch's tree; the source branch retains their history. The 67 MB of ignored legacy `data/` was moved intact to `/home/shahriar/projects/traffic-signal-legacy-data-2026-09-27`. New plans and logs use ignored `data/study/`.

The new study compares fixed at 12 s and 24 s green with priority at 6–24 s, all with 5 s yellow. The submitted report used 12 s fixed and 4 s yellow; its outcomes are separate. Five environments use fixed-duration arrival schedules: balanced moderate, one busy, two busy, high–low–high, and sustained high. Five development seeds per environment are specified; no full study collection has begun.

Validation completed: `python3 -B -m unittest discover -s tests` passed **120 tests** (exit 0). One temporary 16-vehicle development probe ran all three arms sequentially. Each released and crossed all 16 vehicles; read-only analysis with schema 4 accepted measurement and timing, matched all 16 vehicles in both fixed contrasts, and reported delay for all four approaches. Versioned derived files are under `/tmp/traffic_signal_study_probe/probe_medium_seed777/`. The probe exposed and prompted a correction to the timing gate: fixed 12 s and fixed 24 s must be treated as distinct settings despite sharing a controller. This probe is a software validation check, not an independent study result.

Next: inspect a representative longer development plan in each environment and confirm model/clock behavior before collecting all five seeds. Run plans sequentially via `python3 scripts/make_plan.py` and `python3 run_paired.py --plans data/study` only after that check. Preserve failed runs, report plan-level uncertainty by environment and per-direction delay, and show ties or losses. Do not claim calibrated road capacity or VANET performance.
