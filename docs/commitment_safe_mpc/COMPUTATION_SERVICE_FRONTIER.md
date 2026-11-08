# Computation–service frontier (Priority 7 development)

Protocol: matched Insertion / B0 / B1 / M1 (+ ablations) under cooperative `time_limit_seconds` budgets on `build_frontier_suite()` (10/20/30/50 customers + rescue pack), seeds `{3,7,11}`, budgets `{0.05, 0.15, 0.40}` s, ALNS iterations capped at 80 so the deadline binds.

Artifact: `budget_frontier.json` (285 raw runs). Regenerate with:

```bash
python -m safe_time_evrp.commitment_safe_mpc.budget_frontier
# CI-friendly subset:
python -m safe_time_evrp.commitment_safe_mpc.budget_frontier --quick
```

## Axes

- X: cooperative optimize budget / realized optimize seconds  
- Y: mean completed customers (primary), executed distance, `full_calls_avoided`

## Headline (M1 vs B1, 15 case×budget cells)

| Metric | Value |
|--------|-------|
| Cells where M1 mean completed > B1 | **2 / 15** |
| Cells where M1 mean optimize_seconds < B1 | **13 / 15** |
| Replay OK across raw runs | required / observed in study |

M1 consistently avoids full `evaluate_route` in the ALNS hot path (`full_calls_avoided` thousands–tens of thousands) and is usually slightly faster. **That speed rarely converts into more completed customers at the same budget** on this development suite.

## Mean completed @ matched budget (3 seeds)

| Case | Budget | B1 done | M1 done | Δ | B1 opt (s) | M1 opt (s) |
|------|--------|---------|---------|---|------------|------------|
| frontier_10 | 0.05 | 3.00 | 3.00 | 0 | 0.265 | 0.253 |
| frontier_10 | 0.15 | 3.00 | 3.00 | 0 | 0.362 | 0.333 |
| frontier_10 | 0.40 | 3.00 | 3.00 | 0 | 0.347 | 0.331 |
| frontier_20 | 0.05 | 12.00 | 12.00 | 0 | 2.367 | 2.246 |
| frontier_20 | 0.15 | 12.00 | 12.00 | 0 | 6.479 | 6.299 |
| frontier_20 | 0.40 | 12.00 | 12.00 | 0 | 12.330 | 11.673 |
| frontier_30 | 0.05 | 14.33 | 14.00 | −0.33 | 2.972 | 2.820 |
| frontier_30 | 0.15 | 16.00 | 13.00 | −3.00 | 8.047 | 6.569 |
| frontier_30 | 0.40 | 10.67 | 13.00 | **+2.33** | 14.246 | 13.143 |
| frontier_50 | 0.05 | 22.00 | 20.00 | −2.00 | 4.885 | 5.389 |
| frontier_50 | 0.15 | 22.00 | 22.33 | **+0.33** | 12.184 | 14.242 |
| frontier_50 | 0.40 | 22.00 | 21.33 | −0.67 | 28.284 | 25.470 |

Service is often tied (10/20-customer). On 30/50-customer instances, Δ completed flips sign across budgets/seeds — not a stable operational win.

## Reading

Saved suffix evaluations are real. Fixed-budget **service** dominance of M1 over B1 is **not** established. Non-monotonic completed counts vs budget on frontier_30 also show seed/search noise; treat deltas as development signal only.
