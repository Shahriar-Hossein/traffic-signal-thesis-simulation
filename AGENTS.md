# Traffic-signal: Codex working rules

Research data is the product. A completed simulation is not automatically valid evidence.

## Start cheaply

- Read `docs/CODEX_WORKING_STATE.md` for the current checkpoint. Search headings before opening the long handoff/readiness documents.
- Use `python3 -B -m unittest discover -s tests`; check the actual test count and exit code. Bare discovery may find zero tests.
- Python and pygame are installed system-wide. Do not recreate the environment or install dependencies without a concrete need.
- `CLAUDE.md` contains shared project context; do not duplicate long descriptions here.

## Work allocation

- The user authorizes lower-cost delegation for this publication effort. Use Luna for bounded exploration/mechanical changes, Sol or Terra for isolated implementation, and the lead for validity, experimental design and integration.
- Model names are runtime-specific preferences, not price guarantees. Use only models exposed by the current tools. Escalate an agent's task when evidence shows it needs stronger reasoning.
- Give each agent a narrow question, owned files/functions, acceptance tests and a short report format. Prefer a fresh context with explicit relevant paths over copying the whole conversation.
- Agents run scoped tests; the lead runs the integrated suite. Pause tests and other heavy local work during simulator collection.
- Do not delegate a two-command lookup or work already understood by the lead. Avoid overlapping edits. Never run simulator arms concurrently, including from separate agents.
- Do not commit, push, publish or contact others merely because a delegated workflow mentions those actions. Follow the user's actual authorization.

## Evidence invariants

- Use `run_paired.py` for sequential comparisons. `run_simulation.py` is a legacy parallel launcher, not a collection tool.
- Keep raw archives immutable. Run probes in temporary folders and use `write=False` for historical reanalysis.
- Preserve plan hashes and distinguish archived descriptive results from publication-eligible evidence.
- The independent replicate is a traffic plan, not a vehicle, folder name or rerun. Infer per scenario; reused seeds across cells are not independent overall replicates.
- Do not tune on reserved evaluation seeds. Record development seeds, policy/model changes and the analysis contract before collection.
- Do not call discharge proxies capacity, startup lost time or utilisation without the required queue observations.
- A simulator/model/clock change requires new validation and fresh final evidence. Never relabel old experiments as having used new settings.

## Learning and handoff

- Keep durable operational rules here, task-specific procedures in skills, and current progress in `docs/CODEX_WORKING_STATE.md`.
- Add a rule only after a demonstrated problem or repeated workflow. Prefer replacing an obsolete instruction to accumulating warnings.
- Update the checkpoint at completed milestones: changed behavior, exact checks, remaining decisions, next command. Keep historical reviews intact.
- Test periodic boundaries and serialization seams: small plans may never reach a demand transition, and hashes belong to the written plan rather than an assumed in-memory update.
