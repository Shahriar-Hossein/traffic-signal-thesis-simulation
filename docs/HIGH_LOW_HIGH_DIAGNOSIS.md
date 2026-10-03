# High–low–high diagnosis — 2026-10-03

Priority has a small overall mean-delay win over fixed12, with worse tail delay and some approach losses. It has a larger mean-delay win over fixed24. This is a controller tradeoff in the accepted records; the checks below found no selection or green-rule mismatch.

## Reviewed collection

Source: `results/study_collection_20260929_20261002/summary.txt` and its manifest. Thirteen accepted plans: seeds 401, 402, 405, 407–412, and 414–417. Seven excluded plans are outside this diagnosis. Differences are priority minus baseline, in seconds.

| Metric | Versus fixed12 | Versus fixed24 |
|---|---:|---:|
| Mean stopped delay | -0.702 | -13.145 |
| Clearance time | -10.165 | -20.936 |
| Within-plan p95 delay | +6.436 | -26.021 |
| Down mean delay | +4.048 | -2.912 |
| Left mean delay | +4.788 | -25.179 |
| Right mean delay | -2.313 | +5.789 |
| Up mean delay | -9.382 | -30.236 |

Priority wins mean delay in 9/13 plans versus fixed12 and 13/13 versus fixed24. Its p95 loses in all 13 versus fixed12. The mean-delay difference versus fixed12 has a reported 95% CI of [-1.223, -0.158] s; the benefit is small.

## Read-only log diagnosis

Group vehicles by prescribed arrival offset in each plan. Compute each arm's mean stopped delay in each group, then average those means across the 13 plans. These are descriptive breakdowns, without new confidence intervals.

| Arrival group | Fixed12 | Fixed24 | Priority | Priority minus fixed12 |
|---|---:|---:|---:|---:|
| First high, 0–45 s | 27.676 | 40.153 | 26.358 | -1.318 |
| Low, 45–90 s | 31.752 | 34.765 | 25.607 | -6.145 |
| Second high, 90–135 s | 29.948 | 43.562 | 30.558 | +0.610 |

Most vehicles arrive in the two high periods, so a benefit for low-period arrivals contributes little to the overall mean. This scenario changes total arrival intensity while keeping direction assignment even; it does not create a persistently dominant approach.

The controller uses current uncrossed demand weighted by inverse vehicle speed (`utils/counters.py`), grants `clamp(int(0.75 * weight), 6, 24)` seconds (`core/policy.py`), and reorders only approaches still unserved in the round (`core/cycle_priority.py`). It has no arrival forecast, waiting-age score, maximum-red constraint, or early green termination when queues clear.

Priority phases starting during the first high period average 9.51 s green; those starting during the low period average 14.93 s. The larger low-period greens are consistent with clearing queues accumulated in the first surge, rather than immediately following the reduced arrival rate. Phase groups are based on green start; phases may span a demand boundary.

Reordering once-per-round service does not bound the gap between successive services. For each plan and direction, compute the maximum next-green-start minus previous-green-end interval, then average those maxima across plans. Fixed12 is about 56.02 s for every direction; priority is 66.48 s right, 64.47 s down, 68.32 s left, and 66.71 s up.

Concrete example: seed401 priority serves left at 10.004 s for 6 s, 69.021 s for 15 s, then 161.053 s. The latter red interval is about 77.03 s. Fixed12's left red intervals are about 56 s. This supports the observed long-wait penalty.

Across complete phases, fixed12 has only 0.18, 0.54, and 0.74 stopped vehicles on average remaining in the served approach at green end for phases starting in the first high, low, and second high periods. Fixed12 already serves these queues well in this simulator. A low stopped count alone does not prove all demand has crossed or quantify unused green.

## Verification and limits

- All 13 accepted plans have 383 matching vehicle prescriptions crossed in every arm.
- Logged priority greens match the rule, and each selection maximizes logged weight among still-unserved approaches. No mismatches found.
- The IDE's seed301 is a separate development plan. Priority mean delay there is 28.11 s versus fixed12 31.00 s and fixed24 43.45 s; left loses versus fixed12 by 6.72 s. Its p95 improves slightly versus fixed12, unlike the accepted collection average.
- Existing unit suite: 113 tests passed, exit 0. No simulator or raw evidence changed.

These observations explain plausible mechanisms, but do not isolate the causal contribution of ordering versus duration. Next, if improving the controller is requested, compare ordering and duration separately on development plans with fresh output roots. Any controller change requires fresh validation and evidence; do not tune against the final collection and reuse it as confirmation.
