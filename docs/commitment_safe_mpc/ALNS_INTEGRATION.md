# ALNS–MPC integration (Phase C / B0)

**Revision:** B0 hardening on `research/decision-relevant-dual-mpc`  
**Plant:** `FleetSimulator` (unchanged)  
**Controller:** `src/safe_time_evrp/commitment_safe_mpc/alns_mpc.py` → `ReactiveAlnsMpc`

## What was reused

Algorithmic ideas adapted from sibling `MPC_MCTS_Multi_agents_EVRP/evrp/optimizers/alns.py`:

- Destroy operators: random, worst/related/critical-TW style rankings  
- Repair: **greedy** and genuine **regret-2 / regret-3** (customer maximizing \(k\)th-best − best insertion cost among the unassigned pool)  
- Adaptive roulette weights with segment reaction factor  

Decoding and feasibility stay on SAFE_TIME:

- Append-only decode: each next sequence customer is placed only at the **end** of the current service sequence (charge/reload variants allowed before that next service)  
- After a successful decode, sequences are **canonicalized** from the validated route’s service order  
- `environment.physics.evaluate_route` for feasibility  
- `Decision` / `Visit` / `apply_decision` on the authoritative plant  

No wholesale module copy; no change to Schneider physical assumptions.

## Online information boundary

`commitment_safe_mpc/public_snapshot.py` builds a sanitized instance containing only customers already present in the `Observation`. Arcs are **filtered** from the full instance (distance / travel_time / energy / road fields preserved); Euclidean rebuild is not used. Both `EventTriggeredMPC` and `ReactiveAlnsMpc` optimize on that snapshot.

## Acceptance rule

A customer appears in `newly_accepted` only if a fully decoded, `evaluate_route`-validated fleet plan **serves** that customer together with all pending accepted commitments. Incomplete search does not invent acceptances.

## Failure mode

If no feasible incumbent exists: empty suffixes (preserve locked non-interruptible via plant rules), `newly_accepted=[]`, `no_feasible_continuation=True`, audit status **`UNKNOWN`** (never “proven infeasible”). Depot returns are proposed only when `evaluate_route` on the public snapshot proves reachability.

## Planning budget (cooperative)

`decide()` records end-to-end **wall time** (constructor + ALNS + decode + validation). The `time_limit_seconds` deadline is checked **cooperatively between iterations** — it is **not** a hard real-time preemption. Mid-iteration work may overrun the nominal budget.

## Diagnostics tracked

Iterations, candidates evaluated, improvements, rejected moves, route evaluations, constructor vs best distance, first/best feasible times, wall seconds, feasibility status (`UNKNOWN` / feasible incumbent), optimize seconds (on `Decision.audit["alns"]`).

## Commands

```bash
python -m pytest -q tests/test_commitment_safe_phase_c.py tests/test_commitment_safe_b0_b1.py tests/test_commitment_safe_import_cycle.py
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare
python -m safe_time_evrp.evaluation.smoke_test
```

## Known limitations

- Nominal physics only — not a robust safety certificate.  
- Destroy/repair operate on customer sequences; charge placement is via insertion variants during decode.  
- ALNS need not beat insertion on every case; search activity is the Phase C requirement.  
- Cooperative deadline ≠ hard real-time.  
- B1 full-validation witnesses and M1 incremental certificates are **not** the B0 claim (B1 is a separate controller).
