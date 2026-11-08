# Baseline fairness audit

| Requirement | Status |
|-------------|--------|
| Same physical simulator | Yes — `FleetSimulator` |
| Same visible information | Yes — `PublicPlanningSnapshot` for both controllers |
| Same fleet / battery / windows | Yes — shared `BaselineCase` |
| Same acceptance semantics at plant | Yes — `apply_decision` |
| Same objective proxy | Distance (+ charge time lex) under nominal physics |
| Same compute budget knob | ALNS `iterations` + `time_limit_seconds`; insertion is constructive (faster) — reported separately |
| Matched releases / seeds | Yes |
| Independent replay | `validate_log` on every episode |
| No offline full-scenario access | Public snapshot strips unreleased customers |
| No hidden future in observation | Structural + regression tests |

## Asymmetry acknowledged

Insertion is a single constructive pass; ALNS is iterative search with an explicit wall-clock budget. Fairness for **decision quality** uses identical observations and plant. Fairness for **runtime** reports both wall times; do not claim ALNS is faster.

## Not claimed

Robust safety, incremental certificates, or superiority on all instances.
