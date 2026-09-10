# traffic-signal

Pygame microscopic simulation of a four-approach intersection, comparing a
fixed-time signal controller against queue-responsive ones. The output is
research data, so a run that is merely "working" is not necessarily valid.

## Environment (verified 2026-09-10)

- Python 3.12.3 at `python3`, pygame 2.5.2, both **system-wide**.
- **There is no venv and no `requirements.txt` / `pyproject.toml`.** Don't create
  one, don't `pip install -r`, don't go looking for an activate script. Deps are
  already importable.

## Tests

132 tests, about 2 seconds, no display needed:

```bash
python3 -m unittest $(ls tests/test_*.py | sed 's|/|.|;s|\.py$||')
```

**`python3 -m unittest discover` silently finds nothing here** and exits with
"NO TESTS RAN" rather than an error, because `tests/` has no `__init__.py`.
Don't read that as a passing suite. Single module: `python3 -m unittest tests.test_controllers`.

Some tests print simulation-style report output and diagnostic symbols on the way
past. Read the `Ran N tests` / `OK` line at the end, not the noise before it.

## Never run the arms of a comparison in parallel

`run_paired.py` runs arms **sequentially, one process at a time**, and that is a
correctness requirement, not a performance choice. Physics runs inside the
renderer, so two pygame processes competing for CPU and GPU do not get the same
frame rate, and the arm that renders slower has literally slower vehicles. That
confound is indistinguishable from a controller effect.

`run_simulation.py` starts 5 instances in parallel. It predates the paired
design. Do not use it to produce comparison data, and do not copy its pattern.

## Entry points

- `main.py` — one simulation run. Calls `pygame.display.set_mode`, so it needs a display.
- `run_paired.py` — the paired replay harness. This is what produces comparable data.
- `run_simulation.py` — legacy parallel launcher. See above.

## Docs

`docs/` is ~3,100 lines. Grep for the anchor, then read the span; don't full-read these:

- `docs/AGENT_HANDOFF.md` (793) — current state and where work left off
- `docs/THESIS_IMPROVEMENT_PLAN.md` (540)
- `docs/ARCHITECTURE.md` (387)
- `docs/PAIRED_REPLAY_PLAN.md` (382)
- `docs/PUBLICATION_READINESS.md` (355)
- `docs/EXPERIMENT_PROTOCOL.md` (237)
