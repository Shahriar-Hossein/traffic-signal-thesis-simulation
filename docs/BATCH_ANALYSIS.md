# Batch analysis (collection 20260929)

86 valid plans, analyzed per environment with `analyze_batch(..., fps_tolerance=0.10, write=False)`. Nothing was written to the data folders.
Exclusions (14 plans) are in `STUDY_EXCLUSIONS.md`. Heavy environments have fewer plans and lost plans may be the harder ones.

Delta = priority minus fixed. Negative means priority is lower (better). CI is a 95% bootstrap over plan means. "Worse" counts plans where priority was worse.

## Mean stopped delay (s)
| Environment | n | vs fixed12 [CI] | plans worse | vs fixed24 [CI] | plans worse |
|---|---|---|---|---|---|
| balanced_moderate | 20 | -4.18 [-4.64, -3.74] | 0 | -17.20 [-18.20, -16.24] | 0 |
| one_busy (right) | 20 | -46.85 [-47.97, -45.64] | 0 | -39.80 [-40.96, -38.65] | 0 |
| two_busy (up/down) | 18 | -7.72 [-8.78, -6.66] | 0 | -20.11 [-21.27, -18.99] | 0 |
| high_low_high | 13 | -0.70 [-1.22, -0.16] | 4 | -13.15 [-14.02, -12.21] | 0 |
| sustained_high | 15 | -3.51 [-4.27, -2.82] | 0 | -7.83 [-8.60, -7.11] | 0 |

## Clearance time (s)
| Environment | vs fixed12 [CI] | plans worse | vs fixed24 [CI] | plans worse |
|---|---|---|---|---|
| balanced_moderate | -9.70 [-13.22, -6.45] | 1/20 | -36.67 [-42.12, -31.49] | 0/20 |
| one_busy | -128.19 [-138.65, -118.55] | 0/20 | -74.31 [-82.94, -65.71] | 0/20 |
| two_busy | -20.62 [-27.85, -13.49] | 3/18 | -48.93 [-52.29, -44.86] | 0/18 |
| high_low_high | -10.17 [-15.11, -4.67] | 1/13 | -20.94 [-26.80, -15.14] | 0/13 |
| sustained_high | -15.81 [-25.70, -6.30] | 4/15 | -16.40 [-24.18, -8.19] | 3/15 |

## Per-approach delay vs fixed12 (s; CI crossing 0 is not distinguishable from no change)
| Environment | down | left | right | up |
|---|---|---|---|---|
| balanced_moderate | -2.43 [-4.07, -0.90] | -2.14 [-3.68, -0.69] | -3.34 [-4.69, -1.93] | -8.03 [-9.46, -6.66] |
| one_busy | +2.04 [-1.05, 5.20] | +0.84 [-1.87, 3.59] | -55.27 [-56.15, -54.36] | -2.67 [-6.70, 1.01] |
| two_busy | -7.17 [-8.81, -5.58] | **+2.96 [1.68, 4.32]** | +1.07 [-1.21, 3.42] | -15.86 [-18.18, -13.52] |
| high_low_high | **+4.05 [1.52, 6.42]** | **+4.79 [1.70, 7.99]** | -2.31 [-6.58, 1.92] | -9.38 [-13.15, -5.56] |
| sustained_high | -1.02 [-4.42, 2.35] | +0.98 [-2.98, 4.75] | +3.15 [-1.10, 7.76] | -14.85 [-19.51, -10.17] |

## Per-approach delay vs fixed24
Priority is lower on almost every approach. Exceptions: high_low_high right **+5.79 [1.26, 10.17]**; one_busy and sustained_high right not distinguishable from 0 (sustained_high +1.79 [-1.33, 5.34]).

## Losses and ties
- Approaches where priority is worse than fixed12 (CI excludes 0): two_busy left, high_low_high down and left.
- high_low_high p95 wait vs fixed12: +6.44 [5.19, 7.63], worse on 13/13 plans. Mean delay improves but the tail is worse.
- sustained_high p95 vs fixed12: +1.50 [-1.64, 4.57], worse on 8/15. No clear tail win.
- Mean-delay "plans worse" is the complement of favouring plans; no exact ties were reported by the analyzer. Win counts per plan are in the batch output, not re-tabulated here.

## Not done
- No pooled overall CI: the analyzer withholds it (seeds 401–420 are reused across environments, so they are not independent overall replicates). The overall means in the raw output are descriptive only.
- No meaningful-effect threshold is stated yet. Most CIs are narrow against the effects, but high_low_high vs fixed12 (-0.70 s) and several approach deltas are small; decide the threshold before calling them meaningful.
- These results do not separate control logic from reduced lost time (see the lost-time finding).
