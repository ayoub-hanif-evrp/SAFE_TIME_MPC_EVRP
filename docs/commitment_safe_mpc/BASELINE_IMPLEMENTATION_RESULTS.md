# Baseline implementation results (B0)

Artifact: `baseline_comparison.json`  
Command: `python -m safe_time_evrp.commitment_safe_mpc.baseline_compare`

## Controllers

| ID | Implementation |
|----|----------------|
| Insertion MPC | `EventTriggeredMPC` + `construct_routes` (public snapshot) |
| ALNS–MPC (B0) | `ReactiveAlnsMpc` destroy/repair/adapt + `evaluate_route` decode |

Same plant, releases, fleet size, horizon, replan interval, and replay validator.

## Metrics (operational vs diagnostic)

| Field | Meaning |
|-------|---------|
| `executed_distance` | Sum of physical `depart` arcs on the **full** instance (authoritative) |
| `charged_energy` / `executed_charge_time` | From `charge_*` log events |
| `planned_distance_sum_diagnostic` | Sum of `Decision.total_distance` at replan epochs — **not** operational cost |

Do **not** interpret planned-distance sums as operational improvement.

## Summary (frozen suite, post-hardening)

| Metric | Value |
|--------|-------|
| Cases | 5 (includes adversarial over-accept stress case) |
| Both controllers replay-ok | **5/5** |
| ALNS cases with search iterations | **5/5** |
| ALNS cases with incumbent improvements | **1/5** (`B_competing`) |
| Executed distance vs insertion | Matched on this suite (no operational ALNS win claimed) |

Per-case completed sets matched insertion on this suite; ALNS showed search activity everywhere and improved the constructor distance on the competing-assignment case. Executed physical distance did **not** support a prior “~3.5% operational improvement” style claim.

## Phase B scenario

Both controllers complete a feasible closed loop under independent replay on `B_phase_b` (dynamic releases, two EVs). Charging depends on acceptance/routing choices; plant capability was already proven by the Phase B demo controller.

## Hardening checklist (B0)

- Circular import broken (`commitment_safe_mpc` package is docstring-only; plant binds episode lazily).  
- Genuine regret-k repair; append-only decode + sequence canonicalize.  
- Public snapshot preserves filtered arc tables.  
- Safe failure → `UNKNOWN`, no unverified depot returns.  
- Cooperative wall-clock budget documented.

## Interpretation

B0 is a **credible optimizing baseline**, not the paper contribution. Negative or tied executed costs vs insertion are informative. Proceed to B1 with the same ALNS engine under an independent validation gate.
