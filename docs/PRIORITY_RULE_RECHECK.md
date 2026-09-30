# Priority rule recheck (2026-10-01)

Three plans failed "priority selected green disagrees with its rule": two_busy_403, high_low_high_413, high_low_high_420.

## Cause
- The checker recomputes the green from `decision_weight`, which is logged rounded to 4 decimals.
- The controller uses the full-precision weight, and `int(weight * 0.75)` truncates.
- When `weight * 0.75` is almost a whole number, the two sides differ by 1 s.

## Recheck
`scripts/recheck_priority_rule.py` recomputes each green from the full-precision weight in `decision_counts`.
Result: 100 plans, 1252 priority phases, 0 mismatches. The controller follows its coded rule everywhere.

- two_busy_403 and high_low_high_420: checker false alarm (logged 17.3333, true 52/3, granted 13 s).
- high_low_high_413: weight 11.999999999999998 (true 12), so the coded rule gives 8 s. The exact-math rule would give 9 s. This is 1 s on one phase and is a float-noise quirk in the rule as written.

## Not done
- No comparison.json was changed. The three plans stay marked invalid in the raw data.
- Fix for the next study version: log full-precision weights and use `int(round(weight * 0.75, 6))`. This is a simulator change, so it needs fresh validation.
