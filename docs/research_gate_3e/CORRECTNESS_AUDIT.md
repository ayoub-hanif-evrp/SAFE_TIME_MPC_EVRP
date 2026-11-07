# Gate 3E — Correctness audit

Branch: `research/causal-mpc-validation` · Base: Gate 3D `870029d`

| ID | Defect (Gate 3D) | Fix | Regression |
| --- | --- | --- | --- |
| P0-1 | Forecasts reused eval `customer_ids()` / windows | Anonymous train-atom scenarios (`forecast.py`) | `test_hidden_customers_cannot_change_decision` |
| P0-2 | `_finished` ignored pending releases | Continue while `request_release` ≤ `t_max` | `test_staggered_release_does_not_end_early` |
| P0-3 | Horizon claim on stripped forecast service | Executable microscope: A service → S charge | `test_executable_horizon_causality` |
| P0-4 | Accepts without commitment cover; RH solomon_140 broke promises | Admission gate + plant reject fallback | `test_commitment_validator_*`; solomon_140 trace |
| P1-1 | `hash(name)` seeds | `stable_seed` SHA-256 | `test_stable_seed_is_process_independent` |
| P1-2 | Amazon package window overwrite | Aggregate max(ready), min(due) | amazon loader + unit aggregation test |
| P1-3 | Rollout mislabeled as stochastic | `CONTROLLER_LABELS` / docs | matched summary labels |

Gate 3A–3D reports were **not** rewritten.
