# A Reproducible Scheduling Study of Phase Ordering and Green Allocation in a Simplified Traffic-Signal Simulator

**Anonymous manuscript draft for supervisor review — September 2026**

## Abstract

Traffic-signal studies often compare a new policy with one fixed-time setting, making it difficult to tell whether a difference follows from phase ordering, green-duration allocation, or an uncompetitive baseline. This paper specifies a reproducible scheduling study in a simplified four-approach traffic-signal simulator. The main policy serves every approach once per round, ranks remaining approaches by a current speed-weighted count of uncrossed vehicles, and assigns a bounded green from that same decision snapshot. Two ablations separate order from duration. Fixed-24, a planned development-tuned fixed baseline, and a bounded simple-actuated comparator provide additional controls. Replay plans make controller arms face the same releases, turns, lanes, and vehicle types; inference is at the independent-plan level within a scenario, not the vehicle level. Mean stopped delay is primary, with tail delay, approach disparity, and finite-workload clearance reported separately. Results are deliberately pending fresh held-out collection after tuning and the protocol are frozen. The intended contribution is a transparent decomposition and reproducible evaluation design for this simulator, not calibrated road efficiency, field detector performance, network throughput optimality, or connected-vehicle control.

## 1. Introduction

Signal controllers choose both a service order and the time assigned to each movement. These choices are commonly bundled: a controller may favour a large queue and also extend its green. A comparison with one fixed cycle can then show a difference without identifying which decision produced it. In a simplified simulator, the experiment must make this scheduling comparison reproducible and interpretable before it can support simulator-scoped claims.

This work studies the distinction at an isolated, single-approach-at-a-time four-way intersection. The `priority` policy ranks still-unserved approaches by largest weighted uncrossed-vehicle demand and gives a bounded green. Its two ablations hold either order or duration constant. Together with fixed-24 and the planned fixed-tuned and simple-actuated controls, this gives six prespecified arms. We ask research questions, rather than assert an advance in signal-control theory.

**RQ1:** Within this simulator, how do demand-responsive ordering and demand-sized green allocation separately affect plan-level stopped delay?

**RQ2:** Do mean-delay differences coincide with worse p95 delay or a worse-served approach, indicating a tail or service-disparity trade-off?

**RQ3:** Relative to fixed-24, a development-tuned fixed plan, and a simple actuated comparator, which differences persist across prespecified static-skew and offered-rate scenario cells?

The simulator is not calibrated to a road site. Its frame-dependent vehicle physics, geometry, following, and turning rules are part of the experimental model. The study evaluates scheduling under those rules; it does not estimate field capacity, saturation flow, startup lost time, or real-world efficiency.

## 2. Related control concepts and study position

The FHWA *Traffic Signal Timing Manual* defines actuated control as phase time partly determined by detector actuations and gap-out as termination after no calls during a passage interval [1]. It also says detector location and length, speed, volume, passage time, and minimum green require joint tuning. These principles motivate inclusion of a bounded actuated comparator, but do not calibrate its settings.

Queue-responsive control can alter phase selection itself. Varaiya's max-pressure formulation selects stages from movement queues in a network and studies stability and throughput under specified queueing, turning, and saturation assumptions [2]. Our order-sensitive arms are not max-pressure: they operate at one simplified intersection, serve each approach once per round, do not use downstream pressure, and establish no network result.

Connected-vehicle approaches have a different information set. Pandit et al. use VANET-provided individual position and speed, form platoons, and schedule them using an oldest-arrival-first construction [3]. Here, simple actuation is only local simulated presence in a stop-line zone. No packets, communication latency, loss, penetration, routing, or VANET protocol are modeled.

| Family | Information and decision | Relationship to this study |
| --- | --- | --- |
| Fixed-time | Preset rotation and green | `fixed` and planned `fixed_tuned` |
| Simple actuated | Local presence ends a bounded green | `actuated`, simulator scope |
| Queue/pressure responsive | Queue state selects a movement/stage | `priority` changes order; not max-pressure |
| VANET adaptive | Communicated vehicle state supports scheduling | Outside the model |

## 3. Simulator and controllers

The simulator represents right, down, left, and up approaches, each with three incoming lanes. Vehicles have a type, lane, direction, and turn decision. The renderer advances vehicle motion while controller logic runs separately. A shared monotonic run clock records release, crossing, phase, and stopped-delay times. Every controller begins with a 10 s all-red warm-up and uses single-approach phases with a 5 s yellow. These features are shared by arms.

### 3.1 Demand rule and decomposition

At a decision point, an approach's demand is the sum of `1 / configured speed` for its uncrossed vehicles across the three incoming lanes. This is a simulator-specific weighted count, not a measured passenger-car equivalent or field queue estimate. For `priority`, the controller initially ranks all four approaches. After serving one, it recounts and reranks only the still-unserved approaches; each approach is served exactly once per round, but its place can change before its turn. A selected green is

`max(6, min(int(0.75 W), 24))` seconds,

where `W` is the phase's recorded weighted-demand snapshot. The duration is then held for the phase. This preserves the implemented largest-weighted-uncrossed-demand-per-round semantics rather than describing it as an arbitrary queue policy.

| Arm | Order | Green rule | Status and purpose |
| --- | --- | --- | --- |
| `fixed` | right/down/left/up | 24 s | Diagnostic baseline |
| `priority` | rerank remaining approaches by `W` | 6–24 s from `W` | Joint policy |
| `fixed_order_adaptive_duration` | fixed | `priority` duration rule | Duration component |
| `adaptive_order_fixed_duration` | same reranking as `priority` | 24 s | Ordering component |
| `actuated` | fixed | 6–24 s, local presence gap-out | Responsive comparator |
| `fixed_tuned` | fixed | per-approach timing plan | Development-tuned baseline; not selected yet |

`actuated` grants a 24 s ceiling, honours a 6 s minimum, and may end after two elapsed seconds with no local presence. Its approach-wide zone extends 100 simulator pixels upstream of a stop line and is sampled once per controller second. Detection uses the leading vehicle edge in its travel direction and excludes crossed vehicles. This defined observation function has no calibrated equivalence to a loop or video detector: pixel length, sampling, and perfect occupancy are model choices. Fixed rotation remains in force for empty approaches, so this is not a claim of fully-actuated phase skipping, recall, concurrent rings, or coordinated operation.

`fixed_tuned` is intentionally not result-bearing yet. Its timing table must be selected only from declared development plans, recorded with its selection procedure, and frozen before evaluation seeds are used. Until then it is a supported arm, not a tuned policy whose performance can be reported.

## 4. Experimental design and analysis plan

Each controller arm replays the same finite vehicle plan sequentially. A plan contains releases, vehicle attributes, and turns, so matching plan sequence rows identify the same offered vehicle across arms. The workload ends only after every planned vehicle crosses its stop line. `last_crossing_sec` is clearance; the brief display drain afterward means run duration is not substituted for it.

Scenarios cross direction-demand skew with offered arrival-rate regimes, producing 12 prespecified cells. Skew sets static probabilities by which approaches receive vehicles; it does not make the busiest direction change during a plan. The regime controls total offered arrival timing: pinned low, medium, and high rates are separate cells, and a changing regime varies total offered demand over time. Thus “changing demand” means dynamic total arrivals, not dynamic directional skew. A claim about a changing dominant approach would require a different plan design. Offered-rate labels do not imply calibrated load, capacity, or saturation.

Mean stopped delay per plan is the primary endpoint. It is time stopped in this simulator, distinct from release-to-stop-line travel and clearance. Safeguards are p95 stopped delay, the mean delay of the worst-served approach, and the gap between the best- and worst-served approach. Clearance and travel are reported alongside, not folded into, stopped delay. Vehicles divided by clearance is a transformation of finite-workload completion, not a capacity estimate.

The inferential unit is an independent traffic plan within one of the 12 scenario cells, not a vehicle or rerun folder. Vehicles interact within a run, so their paired differences cannot provide independent replication. The prespecified summary is a plan-level paired mean difference with a 95% percentile bootstrap interval, reported separately for each cell. Pooled summaries across heterogeneous cells are descriptive, particularly when seeds are reused. The final number of independent plans per cell is still a planning decision and will be justified from development variability and the target interval precision before collection. Before analysis, a pair must pass checks for plan identity/hashes, controller mapping, configuration and source provenance, complete crossings, comparable release/frame timing, and phase-log completeness. Invalid pairs remain counted with reasons.

Development seeds may support implementation checks, fixed-plan selection, and replication planning. Reserved evaluation seeds must not be inspected for tuning. Final collection will run arms one at a time and retain raw plans/logs, commands, configuration, source fingerprints, analysis version, and runtime information. Before held-out collection, the protocol must freeze the fixed-timing selection rule, seed allocation, replication target, failure/retry handling, and validity thresholds.

## 5. Results

No final results are reported in this draft. Historical pilot material predates material timing, collection, and comparator work and is development-only; it is not used for an effect size, figure, table, or conclusion. This section will be populated only after the protocol and `fixed_tuned` selection are frozen and all scheduled arms are collected under validated sequential replay.

Final reporting will give, for each scenario and contrast, independent valid plans and failures, absolute stopped-delay values and plan-level paired effects with intervals, p95 and approach safeguards, clearance, travel, and phase/green mechanism distributions. Ablation contrasts will be interpreted as evidence about these implemented ordering and duration components, subject to uncertainty and safeguards, not as evidence that either component universally dominates.

## 6. Threats to validity and scope

Vehicle motion is frame-dependent, so rendering performance can change physics; frame-rate and release telemetry are validity evidence, not decoration. The geometry, following, turning logic, and vehicle types are uncalibrated software choices. The weighted demand count depends on configured speed, rather than observed discharge. The detector is perfect, local, and 1 Hz in pixel coordinates, with no installation constraints, false/missed calls, or call memory. The controller lacks pedestrian service, multi-ring concurrency, phase skipping in the actuated arm, network coordination, downstream pressure, and communication mechanisms.

Finite workloads also differ from sustained operation: arrivals stop and every valid arm drains. Clearance cannot establish steady-state capacity or corridor performance. Paired replay removes offered-plan differences between arms but does not remove model error or hardware timing effects. This study supports reproducible simulator-scoped comparisons only; calibrated traffic/detection validation would be necessary for road-efficiency claims.

## 7. Conclusion

This manuscript specifies a scheduling evaluation in a simplified simulator. Its central question is whether changing phase order, green duration, or both explains any plan-level stopped-delay difference, and whether a difference carries a tail or service-disparity cost. Fixed-24, fixed-tuned, ablation, and bounded-actuated arms make this more discriminating than one fixed-versus-priority comparison. The conclusion remains contingent on frozen fresh evidence. The contribution is a reproducible experimental decomposition with explicit scope, not an untested claim of field realism or connected-vehicle control.

## References

[1] Federal Highway Administration. *Traffic Signal Timing Manual*, 2008, Chapters [4](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter4.htm) and [5](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm).

[2] P. Varaiya. “[Max pressure control of a network of signalized intersections](https://doi.org/10.1016/j.trc.2013.08.014).” *Transportation Research Part C*, 36, 177–195, 2013.

[3] K. Pandit, D. Ghosal, H. M. Zhang, and C.-N. Chuah. “[Adaptive Traffic Signal Control With Vehicular Ad hoc Networks](https://doi.org/10.1109/TVT.2013.2241460).” *IEEE Transactions on Vehicular Technology*, 62(4), 1459–1471, 2013.
