# Scientific verdict (post Priority-7 frontier)

**Question:** Have we obtained a mathematically sound M1 that actually avoids substantial computation and improves commitment-safe D-EVRP decisions under limited MPC time?

**Answer (from code + tests + frontier study):** **Partially — compute yes; decision quality not established.**

### Fixed

1. **False certificates:** onboard/locked-destination can no longer mark commitments covered (`test_m1_correctness_repair.py`).  
2. **Freight-aware prefix theorem:** depot manifest mismatch blocks false reuse.  
3. **Real incremental hot path:** suffix `propagate_from_state` without full `evaluate_route` on the candidate; counters track visits reused/recomputed and `evaluate_route_calls`.  
4. **Event advancement:** certificates truncate completed services and update anchors instead of requiring identical timestamps.  
5. **Profiles:** episode aggregates from every decision audit.

### Priority-7 frontier evidence (`budget_frontier.json`)

- Suite: 10/20/30/50-customer tight-SOC dynamic cases + rescue pack; budgets 0.05/0.15/0.40 s; seeds 3/7/11; matched Insertion/B0/B1/M1(+ablations); 285 runs.  
- M1 faster than B1 on **13/15** case×budget cells; thousands–tens of thousands of `full_calls_avoided`.  
- M1 higher mean completed than B1 on only **2/15** cells; several cells show M1 worse (e.g. frontier_30 @ 0.15 s: −3 completed).  
- Conclusion: incremental eval is genuine and usually cheap; **saved compute does not reliably buy better service under fixed budgets on this suite.**

### Not established

- Stable service/reliability dominance vs B1 under fixed compute.  
- Novelty beyond standard resource-prefix techniques; event-aware advancement remains the candidate distinction without large-scale holdout evidence.  
- Robust recursive feasibility under disturbance.

### Remaining scientific blocker

Need either (a) regimes where extra ALNS iterations from saved evals systematically improve accept/charge decisions, or (b) a different mechanism that changes the decision set — not only the inner evaluator. Non-monotonic completed vs budget on frontier_30 also flags seed/search variance; larger multi-seed campaigns required before any paper claim.

**Paper claim:** still **NOT YET**.
