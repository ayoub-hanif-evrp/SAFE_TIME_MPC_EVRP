# MPC terminal correctness audit

## Problem A — horizon-end freeze

`freeze_simulator_at_horizon` advances the plant clock to exactly `t+H`.
Partial noninterruptible actions that straddle the boundary keep locks:

- Travel: proportional SoC drain; remain TRAVELING at origin with reduced residual.
- Charge: proportional SoC accumulation; remain CHARGING.
- Service: remain SERVING; completion only at locked `service_end`.

## Problem B — residual obligations

Residuals are taken from the **simulated terminal observation**:
`accepted ∪ in_service − completed` (not `candidate.accepted`).
Includes first-stage accepts, scenario-recourse accepts, and locked in-service.

## Tests (`tests/test_terminal_horizon_correctness.py`)

- No event before horizon end
- Partial travel / charging across horizon
- Recourse acceptance reflected in residuals
- Stranded terminal battery
- Terminal service deadline expiration
- Stage-0 Validate OK with terminal infeasible counterexample

## Approximation class

Schneider plant has no continuous path geometry. In-transit state is
origin-node + proportional energy. Conservative for SoC and reachability.
Documented; not claimed as exact continuous-space projection.

## Gate

Terminal gate marked passed only after the unit tests above succeed.
