# Gate 3B — Multistage oracle corrections

Git base for this gate: branch `research/realdata-mpc-gate` from
`research/multistage-viability-gate` @ `5ab9e9c` (Gate 3A NO-GO).

## Bugs repaired

1. **Search caps must not return `PROVEN_INFEASIBLE`.**  
   `open_loop_feasible` / `two_stage_fixed_route_feasible` now return `TIME_LIMIT` when
   enumeration caps bind before the queue is exhausted. Exhaustive empty search still
   returns `PROVEN_INFEASIBLE`.

2. **Budget-exceeding histories are outside the uncertainty set.**  
   Open-loop and two-stage now filter mode tuples with `path_combo_admissible` (residual
   `z` along the traveled path). A plan is no longer marked failed because an
   inadmissible double-high path cannot be executed.

3. **Shared uncertainty contract** documented in `oracle.py` and applied consistently to
   open-loop, two-stage, feedback (admissible modes at the current residual), and
   clairvoyant (exclude worlds with total `z > gamma`).

4. **CEX-2 withdrawal.**  
   `budget_reset_sensitive` used `z=1`-only arcs (no nominal). That is a pathological
   forced-deviation plant, not a standard budgeted uncertainty set. Gate 3A claim that
   residual reset creates a false certificate **under Bertsimas–Sim budgeted uncertainty**
   is **withdrawn**. The toy is retained as
   `budget_reset_sensitive_pathological` for regression only.  
   Replacement negative control: `standard_budgeted_has_nominal` (always has `z=0`).

5. **Nonanticipativity.**  
   Added a test that identical information states (same observation history) yield the
   same feedback action, beyond mere mode-label renaming.

## Preserved Gate 3A negative findings

- Routing-fork gap (CEX-1) still holds under the corrected contract.
- Adaptive charge alone is not novelty (N2).
- Feedback is useless on N1.
- Terminal-viability “certificate” remains identical to feedback DP (no theorem).
- Overall Gate 3A decision remains **NO-GO** for that novelty hypothesis.
