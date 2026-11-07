# Computational scaling study

Generator (frozen): `dr_dual/generic/instance_gen.py` (`FROZEN_SEEDS`)  
Runner: `python -m safe_time_evrp.dr_dual.generic.compute_scaling`  
Artifact: `computational_scaling.json`

## Comparisons

1. Unpruned exact first-action search (`use_pruning=False`)
2. Clairvoyant-bound pruning
3. Generic TEI resource-bound pruning
4. Combined sound bounds
5. Baselines: robust / passive / info-gain (decision quality)

## Metrics

Exact agreement, prune counts, total heavy ops, mean wall time, time-reduction fraction vs unpruned.

**Screening target:** median ≥20–30% total runtime reduction on nontrivial instances — research criterion, not a publication guarantee.

## Interpretation rule

Do not claim scalability from millisecond noise. Prefer heavy-op and wall-time medians across the frozen suite. Report negatives.
