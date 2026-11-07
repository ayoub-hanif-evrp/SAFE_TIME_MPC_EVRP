# Computational scaling study

**Important:** The committed pre-repair artifact on eight frozen seeds (all exact value **9.75**, all first action `D_N0_exploit`) is **not** a valid behavioral scalability experiment. It remains historical negative evidence that pruning did not reduce heavy ops (0/8) under that degenerate suite.

## Current development runner

Generator: `dr_dual/generic/discriminating_suite.py` (D1–D4)  
Runner: `python -m safe_time_evrp.dr_dual.generic.compute_scaling`  
Artifact: `computational_scaling.json` (regenerated on the discriminating suite)

## Comparisons (same initial state / belief / noise / policy class)

1. Unpruned exact first-action search (`use_pruning=False`)
2. Clairvoyant-bound pruning
3. Generic mode → **trivial safe reward UB** (quarantined TEI must not prune)
4. Combined min of sound `VALID_BOUND`s
5. Baselines: robust / passive / info-gain (decision quality)

## Metrics

Exact agreement, prune counts, total heavy ops, mean wall time, time-reduction fraction vs unpruned; first-action diversity across instances; exact status scope.

**Screening target (unchanged research bar):** median ≥20–30% total runtime reduction on *nontrivial, discriminating* instances — not a publication guarantee.

## Latest discriminating-suite snapshot

From regenerated `computational_scaling.json`:

| Instance | Exact first | Exact value | Status |
|----------|-------------|-------------|--------|
| D1_multi_accept | `D_N0_exploit` | **14.625** | `EXACT_OPTIMUM_RESTRICTED` |
| D2_two_ev | `D_N0_exploit` | **17.45** | `EXACT_OPTIMUM_RESTRICTED` |
| D3_charge | `D_N0_exploit` | **9.65** | `EXACT_OPTIMUM_RESTRICTED` |
| D4_info | `D_N0_inform` | **12.525** | `EXACT_OPTIMUM_RESTRICTED` |

Values and first actions are **no longer identical**. Info-gain heuristic selects `D_N0_inform` on D1 where exact prefers exploit. Generic/trivial-bound mode: 2/4 exact agreement; **0/4** heavy-op improvement; median time reduction **negative** (~−2.8%). Screening target still **failed**.

## Interpretation rule

1. Do not claim scalability from the old 8×9.75 suite.
2. Do not claim acceleration if bound evaluation costs more than it saves.
3. Prefer heavy-op and wall-time medians; report negatives.
4. Only compare methods after the oracle status matches the declared policy class.
