# Scientific verdict (post M1 repair)

**Question:** Have we obtained a mathematically sound M1 that actually avoids substantial computation and improves commitment-safe D-EVRP decisions under limited MPC time?

**Answer (from code + tests + development runs):** **Partially.**

### Fixed

1. **False certificates:** onboard/locked-destination can no longer mark commitments covered (`test_m1_correctness_repair.py`).  
2. **Freight-aware prefix theorem:** depot manifest mismatch blocks false reuse.  
3. **Real incremental hot path:** suffix `propagate_from_state` without full `evaluate_route` on the candidate; counters track visits reused/recomputed and `evaluate_route_calls`.  
4. **Event advancement:** certificates truncate completed services and update anchors instead of requiring identical timestamps.  
5. **Profiles:** episode aggregates from every decision audit.

### Not established

- Robust speedup vs B1 on the five tiny cases (often still similar wall time because ALNS search dominates).  
- Better completed-service at fixed budget on large instances.  
- Novelty beyond standard resource-prefix techniques; event-aware advancement is the candidate distinction, not yet a published theorem with large-scale evidence.

### Remaining computational blocker

Even with real suffix propagation, ALNS still evaluates many candidates (destroy/repair decode). Gains appear only when prefixes are frequently reusable *and* budgets are tight enough that saved evals convert into extra search. Profile `full_calls_avoided` / `suffix_visits_recomputed` in `compute_bottleneck_profile.json` before claiming a frontier win.

**Paper claim:** still **NOT YET**.
