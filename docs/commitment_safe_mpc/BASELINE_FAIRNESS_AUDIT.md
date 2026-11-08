# Baseline fairness audit

| Requirement | Status |
|-------------|--------|
| Same physical simulator | Yes — `FleetSimulator` |
| Same visible information | Yes — `PublicPlanningSnapshot` for both controllers |
| Arc physics preserved in snapshot | Yes — filtered original `Arc` records (not Euclidean rebuild) |
| Same fleet / battery / windows | Yes — shared `BaselineCase` |
| Same acceptance semantics at plant | Yes — `apply_decision` |
| Same objective proxy | Distance (+ charge time lex) under nominal physics |
| Same compute budget knob | ALNS `iterations` + cooperative `time_limit_seconds`; insertion is constructive (faster) — reported separately |
| Matched releases / seeds | Yes |
| Independent replay | `validate_log` on every episode |
| No offline full-scenario access | Public snapshot strips unreleased customers |
| No hidden future in observation | Structural + regression tests |
| Operational cost metric | `executed_distance` from depart logs (not planned objective sum) |

## Asymmetry acknowledged

Insertion is a single constructive pass; ALNS is iterative search with an explicit cooperative wall-clock budget. Fairness for **decision quality** uses identical observations and plant. Fairness for **runtime** reports both wall times; do not claim ALNS is faster.

## Not claimed

Robust safety, incremental certificates, operational superiority on all instances, or hard real-time deadline enforcement.
