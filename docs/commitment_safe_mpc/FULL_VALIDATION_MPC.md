# B1 — Full-Validation Commitment-Safe MPC

**Controller:** `src/safe_time_evrp/commitment_safe_mpc/full_validation_mpc.py` → `FullValidationAlnsMpc`  
**Validator:** `continuation_validate.validate_continuation`  
**Search engine:** composed `ReactiveAlnsMpc` (same B0 ALNS; not a forked optimizer)

## Per-epoch procedure

1. Build **public snapshot** only (no unreleased customers).  
2. Run ALNS candidate search under the same `iterations` / cooperative `time_limit_seconds` knobs as B0.  
3. **Independently** validate the candidate with `validate_continuation`: unique assignment of every pending accepted (+ proposed new) customer; no unreleased/rejected service; windows/capacity/SOC/charge/depot return via `evaluate_route`; locked destinations respected; no duplicates.  
4. Accept into `newly_accepted` **only** if validation passes for commitments ∪ {new}.  
5. Incumbent reuse only after revalidation against current anchors; on failure/timeout use the best already-verified continuation for this state (else empty / `UNKNOWN`).  
6. Decision audit status: `CERTIFIED_FEASIBLE` | `UNKNOWN` | `MODEL_CONTRACT_VIOLATED`. There is **no** `CERTIFIED_INFEASIBLE` without a true infeasibility proof.  
7. Validation wall time is counted inside `Decision.optimize_seconds`.

## What “certified” means here

Nominal-physics continuation witness under the public observation. **Not** robust recursive feasibility against energy/time disturbances or future demand.

Locked vehicles must propose an **empty** suffix. Finite `station_capacity` is refused (`MODEL_CONTRACT_VIOLATED`) because the plant has no charger queue. Per-decision validation timing uses `validation_seconds_this_decision` (not summed cumulatives). Independent `primitive_route_check` cross-checks small routes; log replay does not prove unused future suffixes.

## Commands

```bash
python -m pytest -q tests/test_commitment_safe_b1.py
python -m safe_time_evrp.commitment_safe_mpc.baseline_compare --b1
```

Artifacts: `baseline_comparison_b0_b1.json`, `B1_CORRECTNESS_RESULTS.md`, `REVALIDATION_COST_PROFILE.md`.
