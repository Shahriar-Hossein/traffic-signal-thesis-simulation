# Related-work notes: bounded actuated comparator

## Scope of this comparator

The `actuated` arm is a deliberately simple, isolated-intersection comparator:
one approach at a time in a fixed right/down/left/up rotation, a 6 s minimum
green, a 24 s maximum green, and gap-out after two elapsed seconds with no
presence in its approach-wide stop-line zone.  It samples simulator vehicle
geometry once per controller second.  The zone is 100 simulator pixels
upstream of the stop line and observes an uncrossed vehicle's direction-specific
front edge; it does not observe vehicles elsewhere on the screen.

This is an explicit software observation rule, not a model of a calibrated
inductive loop, camera, or detector channel.  In particular, pixels have no
field length, detection errors, call-memory mode, or relation to approach speed;
the model has no communications latency, packet loss, penetration rate, or VANET
network.  It should therefore be called a *simple actuated comparator*, not a
realistic deployment or a VANET simulation.

## Sources and implications

**Federal Highway Administration, _Traffic Signal Timing Manual_, 2008,
Chapters [4](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter4.htm)
and [5](https://ops.fhwa.dot.gov/publications/fhwahop08024/chapter5.htm).**
FHWA defines actuated control as phase time partly controlled by detector
actuations, and gap-out as termination after no calls for a passage interval.
Its guidance makes the coupling important: detector location and length,
approach speed, traffic volume, passage time, and minimum green are tuned
together.  It also distinguishes stop-bar presence detection from upstream
designs and notes that an inappropriate gap can either terminate prematurely or
needlessly extend green.  The study may use the manual to explain the
min/max/gap structure, but must not present 6/24/2 seconds or 100 pixels as
FHWA-calibrated settings.  Field grounding would require stated geometry,
speeds, detector units and placement, call behavior, and a tuning/validation
procedure.

**Pravin Varaiya, “[Max pressure control of a network of signalized
intersections](https://doi.org/10.1016/j.trc.2013.08.014),” 2013.**
This original paper formulates a network of movement queues and selects stages
using pressure, with assumptions including turn ratios and saturation flows; its
result concerns network throughput/stability.  It is relevant because queue
responsive phase selection changes *which* movement is served, not merely green
duration.  A fixed rotation with detector gap-out is therefore not a
max-pressure implementation or a test of its throughput result.  If a paper
compares fixed order, demand order, and gap-out duration, it should report them
as separate controller dimensions rather than describe all as “adaptive.”

**Kartik Pandit, Dipak Ghosal, H. Michael Zhang, and Chen-Nee Chuah,
“[Adaptive Traffic Signal Control With Vehicular Ad hoc
Networks](https://doi.org/10.1109/TVT.2013.2241460),” 2013.**
This original study uses per-vehicle position and speed communicated through a
VANET, forms platoons, and schedules them with an oldest-arrival-first method;
it compares against vehicle-actuated, Webster, and pre-timed methods.  Its
information set and scheduling problem are materially richer than a one-bit,
1 Hz local presence observation.  It supports a motivation for separating
information/control mechanisms, while ruling out claims that this simulator
evaluates connected-vehicle control or replicates VANET benefits.

## Positioning matrix

| Controller family | Information and decision | Equivalent here? |
| --- | --- | --- |
| Fixed-time | fixed sequence and green | Baseline fixed arm |
| Simple actuated | local presence extends/ends green within bounds | `actuated`, at simulator scope |
| Queue/pressure responsive | queue states select movement/stage | Proposed ordering arms only partly overlap; no pressure model |
| VANET adaptive | communicated vehicle position/speed, often platoon scheduling | No |

Claims to avoid: “real-world detector calibration”; “loop-detector-equivalent”;
“network throughput optimal”; “VANET/connected-vehicle evaluation”; and
“fully actuated” if that term would imply phase skipping, recall, concurrent
rings, or calibrated detector behavior absent from the implementation.

The FHWA manual is an engineering guidance source (and its 2008 edition is
archived), not evidence that these simulator settings are appropriate at a
specific site.  Varaiya's analytical network model and Pandit et al.'s VANET
simulation address different observation, movement, and network assumptions;
they ground careful distinctions, not a performance or novelty claim.
