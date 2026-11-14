# Rollout replay contract (decision-epoch forks)

## Purpose

A causal MPC scenario fork must be independently replay-valid without inventing **hidden** future announcements.

## Required history prefix at observation time `t`

For every vehicle:

1. `vehicle_init` at the snapshot node/SOC/load.

For every customer already public in the observation
(`released_open ∪ accepted ∪ completed ∪ rejected ∪ in_service ∪ deferred`):

2. `request_release` at time `t` with `source=decision_epoch_snapshot`.

This reconstructs **information availability** for the fork suffix. It does **not** claim the true historical announcement clock of the plant episode, and it does **not** release still-hidden customers.

For busy vehicles mid-action:

3. Matching remainder evidence (`depart` / `service_start` / `charge_start`) plus scheduled completion events, with residual travel/charge/service time = `anchor.time - t`.

## Forbidden

- Accepting/rejecting a customer with no `request_release` in the fork log.  
- Releasing evaluation-hidden customers into the fork.  
- Suppressing replay failures by filtering decision records.  
- Averaging only the valid scenarios when ranking a candidate (`expected_rollout_value` is fail-closed).

## Score taxonomy

| Outcome | Treatment |
|---------|-----------|
| Replay / simulator failure | Candidate invalid (`-1e9`), explicit `replay_code` |
| Genuinely infeasible action | Dispatch/validation failure, not a silent average |
| Horizon truncation with feasible residual | No AU penalty; residual credit |
| Horizon truncation with infeasible residual | AU / broken-commitment penalty |
| Completed service | `+SERVICE_REWARD` |

## Tests

`tests/test_root_cause_fork_replay.py` — announced accept passes; unreleased accept fails; fail-closed mean.
