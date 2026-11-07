# Baseline comparison (tiny development instances)

```bash
python -c "from safe_time_evrp.dr_dual.experiments import write_artifacts; from pathlib import Path; write_artifacts(Path('docs/decision_relevant_dual_mpc'))"
```

Artifact: `docs/decision_relevant_dual_mpc/small_instance_results.json`

## Single-EV (primary)

| Method | First action | Expansions | Notes |
|--------|--------------|------------|-------|
| Exact dual | DA_inform | — | reference |
| DR dual + DRUB pruning | DA_inform | 2 | pruned useless inform |
| DR dual no pruning | DA_inform | 3 | ablation |
| Robust no learning | exploit-class | — | no VoI |
| Info-gain heuristic | max \|φ₁\| among safe | — | not decision-relevant |

**Primary claim tested:** pruning retains exact first action with fewer expansions (3→2 on this network).

**Secondary:** dual first action differs from optimized passive (inform vs exploit).

## Åkerblom-inspired

Not claimed as a faithful reproduction. A fair navigation-bandit baseline is listed as future work with explicit formulation matching; absent from current tiny delivery/charging oracle comparison.
