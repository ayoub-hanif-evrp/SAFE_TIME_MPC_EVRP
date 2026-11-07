# Gate 3D — Horizon causality microscope

## Question

Does increasing the predictive horizon \(H\) change the **current** first action under the repaired harness when forecasts are information-correct?

## Instance

`mpc3c/horizon_microscope.py` — `horizon_fork`:

- Released at \(t=0\): customer **A** only.
- Forecast: customer **B** with ready time 5.
- Short \(H\) excludes B from planning; long \(H\) includes B.
- Constructive insertion then changes the first stop.

## Result

| \(H\) | Forecast B in plan? | Present first action |
| ---: | --- | --- |
| 1.0 | no | A service |
| 20.0 | yes | B service |
| 20.0 (no forecast) | n/a | A service |

`horizon_changes_present_action = true` (see `causal_summary.json`).

## Information boundary

Flexibility / remaining-set scoring uses only released + accepted + completed/rejected customers plus **explicit forecast samples**. Using `instance.customer_ids()` for unreleased IDs is banned; regression covered in `test_flexibility_score_ignores_hidden_customers`.

## Interpretation

Predictive demand **can** create present-action value on a credible discrete instance. This validates the horizon plumbing; it does **not** by itself validate the flexibility terminal.
