# Experiment protocol

**Status: implementation and development validation; not yet frozen.** Updated
11 September 2026. The user selected a reproducible scheduling study within
this simplified simulator, with a supervisor-ready paper due within September.
Venue selection follows supervisor review. We do not claim calibrated traffic
capacity, real-road efficiency, cross-machine generalization or packet-level
VANET performance. Internal measurement validation and development-only fixed
baseline tuning remain prerequisites for final collection.

## What is being tested

Whether serving the largest queue first, with a green sized to that queue,
reduces stopped delay against a fixed rotation — and where it does not.

The proposed controller changes two things at once against fixed-24: **which**
approach is served next, and **how long** its green lasts. The arms below
separate those.

## Arms

| Arm | Order | Green duration | Role |
| --- | --- | --- | --- |
| `fixed` | fixed rotation | 24 s | diagnostic baseline |
| `priority` | largest queue first, recounted each phase | `max(6, min(int(0.75·W), 24))` | the proposal |
| `fixed_order_adaptive_duration` | fixed rotation | as `priority` | isolates duration |
| `adaptive_order_fixed_duration` | as `priority` | 24 s | isolates ordering |
| `actuated` | fixed rotation | 6–24 s, 2 s sampled detector gap-out | simple responsive comparator |
| `fixed_tuned` | fixed rotation | scenario-specific per-approach constants | development-selected comparator |

`W` is the weighted count of uncrossed vehicles on the approach,
`sum(1 / configured_vehicle_speed)` across its three lanes. Green is computed
once at onset and held.

Yellow is 5 s per phase and phasing is single-approach for every arm.
Total yellow time can differ when policies complete different numbers of phases;
report that overhead rather than claiming total clearance time is constant.

`fairness_priority` is **not** an arm: it changes the duration coefficient, the
upper bound and adds early termination all at once, so it isolates nothing. It
stays available as an exploratory controller.

The actuated comparator samples a 100 px upstream stop-line zone once per
controller second. It keeps the 6 s minimum, grants at most 24 s, and ends
when two sampled elapsed seconds have no detected presence. It serves even
empty approaches in rotation. These are explicit model settings, not calibrated
field detector parameters. The presence test uses the leading vehicle edge.

`fixed_tuned` requires an explicit validated timing table; no missing-cell
fallback exists. Support is implemented, but a table is not called tuned until
development selection completes. The planned candidate set is uniform 12 s,
uniform 24 s and 96 s of total green distributed by directional demand with
6–60 s approach bounds. Selection uses development seeds 301/302 in every
cell and the lowest mean stopped delay; all candidates must have complete valid
coverage. Equal scores follow the predeclared candidate order. The selected
entire table is supplied to all evaluation arms so their configuration
fingerprints remain comparable. This is a bounded search, not globally optimal
fixed timing. Selection and its evidence are archived before evaluation.

## Scenarios

The grid is defined in [`scripts/scenarios.py`](../scripts/scenarios.py) and
crosses demand **skew** with demand **regime**:

| Axis | Levels |
| --- | --- |
| Skew | balanced (0.25 each), moderate (0.35/0.35/0.15/0.15), strong (0.85/0.05/0.05/0.05) |
| Regime | offered 0.5 veh/s, offered 2 veh/s, offered 4 veh/s, changing (switching every 120 s) |

Twelve cells. The regimes are **offered arrival rates**, and nothing more.

They were previously named below / near / over capacity, from fixed-24
clearing 500 vehicles in 248 s on `even_500_seed201` — about 2.0 veh/s. That
is `N / clearance_time` for one finite workload, which this document says
below is *not* a capacity estimate; it cannot be one here either. It averages
over the fill and drain of a queue that never reached steady state, and a
balanced aggregate cannot certify capacity for an 85/5/5/5 allocation under
every controller.

**Capacity is not yet established.** Doing so needs sustained demand held
against a queue criterion, measured per approach and per control policy, and
no such measurement exists in this project. Whether a cell is saturated is
therefore a hypothesis, recorded below with the others, and no
calibrated-traffic claim should be read out of the pilot.

Pinning a regime changes only arrival times **among the three pinned
regimes**: at one seed, the low, medium and high cells draw the identical
sequence of vehicles (direction, lane, type, turn), so demand is the only
thing that varies between them.

This does **not** extend to the changing-demand cell. A mixed plan draws its
condition from the same generator as its vehicles — once at the start and
again at every transition — so it does not share the pinned cells' vehicle
sequence. At seed 301 with N=500 the two differ in the vehicle at 492 of 500
positions. A contrast between the changing cell and a pinned cell therefore
varies the vehicle draws as well as the demand, and must be read that way.
Small samples conceal this: at seed 5 the two agree for 40 vehicles and first
diverge at sequence 60.

**Hypothesis, recorded in advance.** The benefit should be largest under
skewed and changing demand near capacity, where greens sit away from both
bounds. It should shrink under balanced demand, and may vanish or reverse
under sustained overload, where every approach is saturated and ordering
cannot create capacity. Cells where the proposal is expected to lose are part
of the grid deliberately.

## Seeds

- **Development seeds** (301–308): free to inspect, tune against and rerun.
  Earlier inspected seeds 201 and 401/402 are also development-only.
- **Evaluation seeds** (9001–9020): reserved. Run once, after this protocol is
  frozen, and never tuned against.

Any plan reported as evidence names its seed and content hash.

## Workload and run handling

- **Finite workload.** Each plan is exactly 500 vehicles; a run ends when all
  500 have crossed. Clearance time is therefore a measured outcome, not a
  design parameter.
- **Initialization.** Every controller opens with a 10 s all-red so vehicles
  accumulate before the first decision. This warm-up is identical across arms.
- **Arrival cutoff and draining.** Arrivals stop when the plan is exhausted;
  the run continues until the last vehicle crosses. The final 1.5 s of
  rendering after the last crossing is display drain and is excluded — the
  reported clearance is `last_crossing_sec`, not `duration_sec`.
- **Timeout.** 3000 s per arm. A timed-out arm is a **failure**, reported by
  scenario and arm; it is never silently dropped or retried into validity.
- **Residual queues.** Not applicable while the workload is finite and every
  arm clears it. A time-limited study would need residual-queue logging before
  it could be analyzed; that is not this design.

Finite-workload clearance and sustained-flow performance are reported
separately. `N / clearance_time` is a transformation of clearance time, not
independent corroboration and not a capacity estimate.

## Endpoints

| Endpoint | Role |
| --- | --- |
| Mean stopped delay per plan | primary |
| p95 stopped delay | safeguard against tail cost |
| Worst-served approach mean, and the gap between best and worst | safeguard against starving an approach |
| Clearance time (last crossing) | reported separately |
| Entry-to-stop-line travel time | reported alongside delay, because spawn distance depends on the queue ahead |
| Green-duration distribution, bound frequency, discharge span and lane snapshots | mechanism proxies; no utilisation/capacity claim |

## Inference

- **The unit of inference is the plan, not the vehicle.** Vehicles within a
  run interact, so they are not replicates. Each plan contributes one mean
  paired difference.
- **Intervals.** 95% percentile bootstrap on plan-level mean differences,
  fixed seed, reported with the point estimate. Effects are reported **per
  scenario**; a mean pooled across regimes describes none of them.
- **The Wilcoxon statistic is reported but is not the headline.** Its
  assumptions have not been checked at this number of plans; the interval is
  the claim.
- **Replication count** is chosen from pilot variability for a target CI
  half-width, and re-checked once more plans are in.
- **No effect below the noise floor is reportable.** Repeated identical arms
  differ by about 0.01 s of mean stopped delay on this machine; anything of
  that order is jitter, not a result.

## Validity and failures

Every pair passes the gate in
[`analyze_paired.py`](../analyzers/analyze_paired.py) before it contributes:
verified plan hash, matching run identity, matching configuration and source
fingerprints across arms, exactly one crossing per planned vehicle with
matching attributes, finite delays, and comparable frame rates and release
timing. Invalid pairs produce reasons and **no** effect estimate, and are
counted per scenario in the batch summary.

Failures are reported, not excluded. A scenario that fails often is a finding
about that scenario.

### Cohorts

Passing the gate makes a *pair* reportable; it does not make two pairs
poolable. Before plans are aggregated into one interval they must agree on
the controller each arm label ran, the configuration fingerprint, and the
source fingerprint. Plans whose archived content hash has already been seen
are the same run twice, however their folders are named, and are dropped
rather than counted as replication. Where incompatible cohorts are present
the pooled estimate is withheld and each cohort is summarized separately.

Note that seeds are reused across regime cells by design, so a pooled overall
interval across cells cannot treat those observations as independent. Report
per stratum; the overall figure is descriptive.

### Timing acceptance thresholds

These are provisional development acceptance settings, to be frozen before evaluation. They are **provisional** — agreed
here in advance so they cannot be chosen after seeing results, not measured.
Revisit them once §9.5 of [PAIRED_REPLAY_PLAN.md](PAIRED_REPLAY_PLAN.md) has
been measured on a second machine.

| Quantity | Threshold | Disposition when breached |
| --- | --- | --- |
| Frame-rate spread across arms (mean, worst window) | 5% | pair invalid |
| FPS difference on overlapping elapsed intervals, relative to baseline | 5% | pair invalid |
| Worst release lateness, per arm | 250 ms recorded, +100 ms for the vehicle construction that follows the measurement | pair invalid |
| Frame-rate telemetry coverage of each run and common horizon | ≥ 95% | pair invalid or insufficient evidence |
| Completed green overrun beyond granted duration | ≤ 1000 ms (one controller tick) | timing rejected |
| Phase onset drift, two arms of the **same** controller | 1000 ms | timing report rejected |
| Release gap between arms, same vehicle | 500 ms | timing report rejected |
| Greens present in the signal log but missing from the phase log | any | timing report rejected |

Two things are deliberately *not* rejections. Onset divergence between arms
running **different** controllers is a design difference, including between
controllers that share a phase order but not a duration rule; it is reported
as divergence and never as drift. And missing or non-comparable telemetry —
no frame-rate series, no window boundaries, series that do not cover the same
intervals — is reported as **insufficient evidence**, which does not authorize a publication estimate. Both rejection and
insufficient evidence make the pair ineligible, and the driver exits nonzero.

## How to run it

```bash
# 1. See the grid and the commands it expands to.
python3 scripts/scenarios.py --list
python3 scripts/scenarios.py --commands --arms fixed priority

# 2. Run one pair. Arms run one per process, in the order given; the first
#    is the baseline every other is compared against.
python3 run_paired.py --seed 301 --count 500 --uneven-mode even \
    --condition medium --arms fixed priority --timeout 3000

# 3. Analyse. The driver already prints the pair and timing reports;
#    these re-derive them, and aggregate across plans.
python3 analyzers/analyze_paired.py data/paired/even_medium_500_seed301
python3 analyzers/analyze_timing.py data/paired/even_medium_500_seed301
python3 analyzers/analyze_discharge.py data/paired/even_medium_500_seed301/*/
python3 analyzers/analyze_paired.py --batch data/paired --only "even_medium_500_seed*"

# 4. Archive what will be cited.
python3 scripts/export_results.py --name <package> data/paired/<plan_id> ...
```

Set `SDL_VIDEODRIVER=dummy` to run without a display. Runs are CPU-bound and
render physics, so **do not run anything else heavy on the machine while
collecting** — one arm rendering more slowly than its partner is exactly the
confound the frame-rate gate exists to catch.

Each arm writes into `data/paired/{plan_id}/{arm}/`, and the driver refuses to
reuse an existing arm folder, so a rerun needs a fresh arm label or a fresh
plan.

## Reproducibility

Results are exported out of the gitignored `data/` tree with
[`scripts/export_results.py`](../scripts/export_results.py), which records the
plans, raw logs, derived analyses, code revision and the commands used.

## Implementation contract, 11 September 2026

Analysis schema 3 separates raw measurement validity, timing acceptance and
publication eligibility. Only eligible pairs enter batch estimates. Runtime
identity is captured at simulator startup and must agree across arms; later
export dependencies cannot substitute for it. Interval coverage is derived from
recorded start/end boundaries, including the final partial FPS window. The
comparison uses the common elapsed horizon when arms finish at different times;
it does not demand the same number of samples. Resolution remains window-level,
not a proof that sub-window physics was identical.

The driver persists process failures bound to plan identity. Reanalysis cannot
promote such a failure to success from complete-looking logs. Renamed plans and
same-seed reruns do not become independent replicates. Cross-scenario summaries
have no pooled confidence intervals. Explicit output roots and selected plan
IDs keep unrelated historical folders out of collection batches.

Phase CSVs include lane-level uncrossed, stopped and detector-zone counts at
green onset/end, with sample times. Yellow-time shutdown retains the observed
green end; green-time shutdown records a censored snapshot. These snapshots do
not observe continuous queue occupancy or establish saturation flow.

Final replication count is still to be frozen from development precision and
available runtime. The initial planning target is 13 independent plans per cell
(seeds 9001–9013), not an assurance of ±3 s precision for every contrast. No
held-out seed has been used in this implementation/validation stage.
