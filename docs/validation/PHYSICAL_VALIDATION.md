# Physical validation

The simulator and the route evaluator share the nominal energy formula. The replay validator does not call `evaluate_route`. It recomputes Euclidean energy as `r * hypot(dx, dy)` and charge duration as `g * (target - soc)`.

## Model that is enforced

- Service must start inside `[ready, due]`. Waiting is allowed. Service may finish after `due`. This matches the Schneider readme.
- Payload increases only on a depot load whose customers match the recorded demands, and decreases by the customer demand when service starts.
- Battery decreases by the arc energy on arrival and increases only to a target that is at most `Q`, at a charger, for the linear duration.
- Travel, service, and charging cannot overlap for the same vehicle. A second departure before arrival is `interrupted_travel`.
- A service before the customer's release is `early_request_access`.
- The episode-end record must match the replayed node, battery, and load.
- The announced set is every `request_release`. A claimed summary that relabels those customers is `denominator_mismatch`.

Station capacity is unsupported because the benchmark does not define it. Depot handling time is the file's depot service time, which is zero. There is no nonlinear charging curve and no payload-dependent energy.

## Tests

`tests/test_replay_and_episode.py` builds corrupted logs and expects these codes:

| Corruption | Code |
| --- | --- |
| Arrival state of charge below zero | `negative_battery` |
| Service start after the due date | `missed_window` |
| Second service completion | `duplicate_service` |
| Service before release | `early_request_access` |
| Charge at a customer | `impossible_charge` |
| Second departure during travel | `interrupted_travel` |
| Load above `C` | `excess_payload` |
| Arrival node different from the departure destination | `wrong_location` |
| Summary that calls an unserved release completed | `denominator_mismatch` |

The same test runs the easy toy episode twice and checks that the event kinds and final request states match. The development episode on `c101C5` was accepted by this validator (`replay_ok: true` in the local run manifest).

## Unsupported on purpose

- Endogenous charger queues.
- A claim that the nominal `r * distance` model is a field measurement.
- Hard process-level timeouts. Optimization time is a measurement.
