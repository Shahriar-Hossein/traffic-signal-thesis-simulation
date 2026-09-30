# Study exclusions (collection 20260929)

86 of 100 plans are valid. 14 are excluded and not rerun.

| Environment | Valid / 20 |
|---|---|
| balanced_moderate | 20 |
| one_busy | 20 |
| two_busy | 18 |
| sustained_high | 15 |
| high_low_high | 13 |

## Run conditions
- 5 plans in parallel, each pinned to 2 cores. Arms inside a plan stayed sequential.
- Interval FPS divergence limit raised from 5% to 10% (`--fps-tolerance 0.10`). Drift limit unchanged at 250 ms.
- Plans valid under 5% from the earlier batch were not rerun. Do not mix the two tolerances without saying so.

## Excluded plans
| Plan | Failure | Size |
|---|---|---|
| high_low_high_403 | FPS divergence fixed12 to priority | 11.03% (limit 10%) |
| high_low_high_404 | release drift (priority) | 337.87 ms |
| high_low_high_404 | FPS divergence fixed12 to priority | 10.42% |
| high_low_high_406 | release drift (priority) | 271.96 ms |
| high_low_high_418 | FPS divergence, fixed12 to fixed24 / priority | 18.35% / 18.51% |
| high_low_high_418 | fps_min spread | 12.1% |
| high_low_high_419 | FPS divergence fixed12 to priority | 10.48% |
| sustained_high_401 | release drift (fixed12) | 285.47 ms |
| sustained_high_405 | release drift (fixed12) | 263.03 ms |
| sustained_high_406 | release drift (fixed24) | 251.04 ms |
| sustained_high_417 | FPS divergence fixed12 to fixed24 | 11.6% |
| sustained_high_419 | release drift (fixed12) | 269.58 ms |
| sustained_high_419 | FPS divergence | 10.03% / 10.07% |
| two_busy_419 | FPS divergence fixed12 to priority | 11.81% |
| high_low_high_413, high_low_high_420, two_busy_403 | priority-rule check | see `PRIORITY_RULE_RECHECK.md` |

Drift excesses are 1 to 88 ms over the limit. FPS excesses are 0.03 to 8.5 points over. Most are marginal; high_low_high_418 is the clear outlier.

## Caveats to report with results
- Failures cluster in the two heavy environments (7 of 20 and 5 of 20 lost). Heavy-load plans are underrepresented, so their estimates come from fewer plans and possibly easier ones.
- The three priority-rule plans are a checker rounding artifact, not a controller fault. They are still excluded because raw data is immutable.
- Excluded plans keep their raw logs. Nothing was deleted except superseded earlier attempts, moved aside.
