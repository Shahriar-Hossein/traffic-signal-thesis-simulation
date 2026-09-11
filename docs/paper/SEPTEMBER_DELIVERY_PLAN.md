# September supervisor delivery

Agreed scope: a reproducible scheduling study in this simplified simulator.
Deliver the completed conference-paper draft to the supervisor within September
2026; choose a venue after review. Degree-report submission is the priority.

| Target window | Deliverable and completion condition |
| --- | --- |
| 11–12 September | Integrated validity fixes, comparator support, sequential real-run validation; preserve exact source and runtime |
| 12–14 September | Development-only fixed-plan selection, N=500 repeatability and compute measurements; freeze protocol and replication count |
| 14–21 September | Sequential held-out six-arm collection, with all failures retained and analysis per scenario |
| 21–25 September | Final tables/figures, evidence-linked results and discussion, reproducible package |
| 25–27 September | Complete supervisor draft and reconcile descriptions of historical thesis experiments |
| 28–30 September | Supervisor corrections and final submission materials |

These are planning windows, not completed milestones. Collection duration must
be measured at N=500; the 20-vehicle smoke test is not a runtime estimate for
the study. Low demand alone takes about 1,000 s to release 500 vehicles, before
draining, and six arms multiply that cost. Keep arms sequential.

The first precision target under consideration is 13 independent plans per cell,
12 cells and six arms: 936 simulator runs. The balanced historical pilot cannot
guarantee the precision of every new contrast. Freeze the final count after
development planning and before held-out outcomes are examined.

If compute time exceeds the available window, revise the design before touching
held-out outcomes and document the resulting scope. Do not silently omit losing
cells or unsuccessful runs to fit the deadline.

The paper draft exists at `manuscript.md`. It becomes supervisor-ready only when
the pending-results section is replaced by validated evidence, references and
figures are checked, and author details are supplied. A draft of methods alone
does not complete the degree-related submission task.
