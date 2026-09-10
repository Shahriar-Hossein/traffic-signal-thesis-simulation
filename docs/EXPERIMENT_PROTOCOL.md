# Experiment protocol

**Status: draft, not yet frozen.** Two prerequisites remain open — the traffic
model is not calibrated (see [publication readiness](PUBLICATION_READINESS.md)),
and no actuated comparator exists. This document is written before the
evaluation runs so that the design can be read in a diff rather than
reconstructed from whatever was eventually reported.

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

`W` is the weighted count of uncrossed vehicles on the approach,
`sum(1 / configured_vehicle_speed)` across its three lanes. Green is computed
once at onset and held.

Yellow is 5 s and phasing is single-approach for every arm, so clearance is
constant across arms and cannot explain a difference.

`fairness_priority` is **not** an arm: it changes the duration coefficient, the
upper bound and adds early termination all at once, so it isolates nothing. It
stays available as an exploratory controller.

Two gaps, stated rather than hidden:

- **No tuned fixed baseline.** Fixed-24 is a diagnostic, not a competitive
  control. A fixed plan with tuned splits, tuned on development seeds only,
  is still to be added.
- **No actuated comparator.** Comparing only against fixed timing overstates
  what any queue-responsive rule contributes.

## Scenarios

The grid is defined in [`scripts/scenarios.py`](../scripts/scenarios.py) and
crosses demand **skew** with demand **regime**:

| Axis | Levels |
| --- | --- |
| Skew | balanced (0.25 each), moderate (0.35/0.35/0.15/0.15), strong (0.85/0.05/0.05/0.05) |
| Regime | below capacity (0.5 veh/s), near capacity (2 veh/s), over capacity (4 veh/s), changing (switching every 120 s) |

Twelve cells. Regimes are placed against **measured** capacity: fixed-24
cleared 500 vehicles in 248 s on `even_500_seed201`, about 2.0 veh/s through
the intersection.

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
| Green-duration distribution, bound frequency, utilisation | mechanism |

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
