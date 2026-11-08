# Baseline implementation results (B0)

Artifact: `baseline_comparison.json`  
Command: `python -m safe_time_evrp.commitment_safe_mpc.baseline_compare`

## Controllers

| ID | Implementation |
|----|----------------|
| Insertion MPC | `EventTriggeredMPC` + `construct_routes` (public snapshot) |
| ALNS–MPC (B0) | `ReactiveAlnsMpc` destroy/repair/adapt + `evaluate_route` decode |

Same plant, releases, fleet size, horizon, replan interval, and replay validator.

## Summary (frozen suite)

| Metric | Value |
|--------|-------|
| Cases | 4 |
| Both controllers replay-ok | **4/4** |
| ALNS cases with search iterations | **4/4** |
| ALNS cases with incumbent improvements | **1/4** (`B_competing`) |

Per-case completed counts matched insertion on this suite; ALNS showed search activity everywhere and improved the constructor distance on the competing-assignment case.

## Phase B scenario

Both controllers complete a feasible closed loop under independent replay on `B_phase_b` (dynamic releases, two EVs). Charging depends on acceptance/routing choices; plant capability was already proven by the Phase B demo controller.

## Interpretation

B0 is a **credible optimizing baseline**, not the paper contribution. Negative or tied service counts vs insertion are informative. Proceed to B1 only after this interface stays green.
