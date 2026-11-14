# Research history (concise)

## Recovery archive

**Tag:** `archive/pre-repository-cleanup-2026-11-14`  
**SHA:** `a0cb460b3bef26a40d22ac53dff2150ef0a5548d`  
**Branch tip archived:** `research/commitment-safe-predictive-mpc`

Checkout the tag to restore superseded Phase / Gate documentation trees (`docs/research_gate_*`, `docs/commitment_safe_mpc`, dual-MPC exploratory docs, etc.) that were removed from the working tree during repository cleanup.

## Lineage (high level)

1. Plant, replay, insertion MPC, Part 2 certificates / triggers.  
2. Commitment-safe ALNS path → **B1** / **M1** certificate store.  
3. MPC-central action causality, decision regret, Phase 3B–3D validity repairs.  
4. Accelerated pilot + root-cause underserving repairs.  
5. Phase 3E fairness (proposed ≡ stochastic under matched seeds).  
6. Phase 3F switching (regret floor) → **REVISE**.  
7. CC-E-MPC (expected value + hard certificates) → **CERTIFICATE_ONLY**.  
8. Publication integrity closeout → **INCREMENTAL_RESULT**.  
9. Repository cleanup: consolidate onto **`main`**.

## Obsolete remote research branches (deleted after ancestor check)

All were ancestors of `a0cb460` and remain reachable from `main` / the recovery tag:

- `research/causal-mpc-validation`
- `research/closedloop-repair-gate`
- `research/commitment-cost-mpc-gate`
- `research/decision-mpc-gate`
- `research/decision-relevant-dual-mpc`
- `research/experimental-validity-gate`
- `research/multistage-viability-gate`
- `research/realdata-mpc-gate`
- `research/safe-dual-mpc`
- `research/commitment-safe-predictive-mpc` (removed after promotion to `main` and CI green on cleanup)

## Final scientific label

See `docs/paper/PUBLICATION_READINESS_REPORT.md`: **INCREMENTAL_RESULT**.
