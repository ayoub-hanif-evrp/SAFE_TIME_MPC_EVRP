# Correction after independent audit (post-`e1f9f0a`)

## Withdrawn / repaired claims

| Issue | Status |
|-------|--------|
| `min_θ max_π` used as incumbent L | **Removed.** L seeded only from executable Bayes value of a concrete first action + nonanticipative common continuation. |
| `_realize_robust_continuation` picking best plan per true θ | **Repaired.** `select_common_policy` chooses one plan from the belief only; true θ only realizes that plan. |
| Zero-VoI via equal known-θ optima | **WITHDRAWN_UNSOUND.** Must not prune. See P1/P2 counterexample (`abstract_p1_p2_counterexample`). |
| Commitment = still accepted | **Repaired.** Require `accepted ⊆ completed`. |
| `busy_until` no-op | **Repaired.** Rejects actions while busy. |
| Clairvoyant plan builder receiving θ | **Repaired** in `commitment_safe_under_all_theta`. |

## P1/P2 logical counterexample

```
min_θ max_π R = 10
max_π min_θ R = 0
max_π E[R]     = 5
```

A false L=10 could prune a sound candidate with Q̄=7; true executable L=5 must not.

## Still open

- Two-EV shared-time observation gate: not yet a demonstrated cross-vehicle win.
- Resource envelope UB often fails to dominate clairvoyant DRUB → **not used for certified prune** unless `sound_resource_ub_vs_clairvoyant`.
- Clairvoyant DRUB remains a standard perfect-information relaxation (reference UB).

## Assessment change

Previous `PROMISING METHOD` at `e1f9f0a` is **withdrawn pending this repair**.  
Current status: **CORRECTED PROTOTYPE — CONDITIONAL PROMISE** (see `SCIENTIFIC_STATUS.md`).
