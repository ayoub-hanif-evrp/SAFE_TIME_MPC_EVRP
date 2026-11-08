# ALNS–MPC integration (Phase C / B0)

**Revision:** see git HEAD on `research/decision-relevant-dual-mpc`  
**Plant:** `FleetSimulator` (unchanged)  
**Controller:** `src/safe_time_evrp/commitment_safe_mpc/alns_mpc.py` → `ReactiveAlnsMpc`

## What was reused

Algorithmic ideas adapted from sibling `MPC_MCTS_Multi_agents_EVRP/evrp/optimizers/alns.py`:

- Destroy operators: random, worst/related/critical-TW style rankings  
- Repair: greedy / regret-style insertion ranking  
- Adaptive roulette weights with segment reaction factor  

Decoding and feasibility stay on SAFE_TIME:

- `optimization/insertion._variants` + `environment.physics.evaluate_route`  
- `Decision` / `Visit` / `apply_decision` on the authoritative plant  

No wholesale module copy; no change to Schneider physical assumptions.

## Online information boundary

`commitment_safe_mpc/public_snapshot.py` builds a sanitized instance containing only customers already present in the `Observation`. Both `EventTriggeredMPC` and `ReactiveAlnsMpc` optimize on that snapshot.

## Acceptance rule

A customer appears in `newly_accepted` only if a fully decoded, `evaluate_route`-validated fleet plan **serves** that customer together with all pending accepted commitments. Incomplete search does not invent acceptances.

## Diagnostics tracked

Iterations, candidates evaluated, improvements, rejected moves, route evaluations, constructor vs best distance, first/best feasible times, optimize seconds (on `Decision.audit["alns"]`).

## Commands

```bash
python -m pytest -q tests/test_commitment_safe_phase_c.py
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare
```

## Known limitations

- Nominal physics only — not a robust safety certificate.  
- Destroy/repair operate on customer sequences; charge placement is via insertion variants during decode.  
- ALNS need not beat insertion on every case; search activity is the Phase C requirement.  
- B1 full-validation witnesses and M1 incremental certificates are **not** implemented here.
