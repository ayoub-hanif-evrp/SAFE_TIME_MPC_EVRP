# Final MPC formulation — Certificate-Carrying Economic MPC (CC-E-MPC)

> **Research refocus (2026-11):** The paper track’s **proposed method** is now
> Commitment-Safe Stochastic MPC — see
> `docs/methodology/COMMITMENT_SAFE_STOCHASTIC_MPC.md`,
> `docs/proofs/RECURSIVE_FEASIBILITY_STOCHASTIC_MPC.md`, and
> `src/safe_time_evrp/mpc_central/commitment_safe_stochastic_mpc.py`.
> CC-E-MPC (especially greedy-nominal) remains a **named baseline**, not the
> proposed contribution. Do not proliferate BAP/DF-BAP-style wrappers.

**Assessment: `CERTIFICATE_ONLY` (historical CC-E baseline track)**

Parent SHA: `9f075541`. Holdout frozen. Phase 3F worst-scenario regret floor is **retired**.

## Control law

Maintain a persistent `ContinuationCertificate` (executable routes + anchors + accepted set).

At every decision event:

1. Observe public information only.
2. Advance the certificate through realized noninterruptible events; revalidate or invalidate.
3. Generate competing first actions (serve / accept / reject / charge / wait / ALNS–B1 proposals).
4. **Hard filter:** reject any candidate that fails nominal commitment feasibility for existing + newly accepted obligations.
5. Score feasible candidates with shared forecast scenarios and causal B1-validated recourse.
6. Select the maximum **expected economic value** (service reward − AU penalty − distance).
7. Execute the first physical action; publish the new verified certificate.
8. On timeout / no valid score / invalid new plan: execute the verified fallback certificate.

### Critical distinction

| Constraint | Status |
|------------|--------|
| Nominal commitment feasibility | **HARD** |
| Reward ≥ B1 in every forecast scenario | **NOT** a safety constraint (removed) |

Objective weights are the plant’s existing constants (`SERVICE_REWARD=100`, `UNFULFILLED_PENALTY=250`, `DISTANCE_PENALTY=1`). They were not tuned on winning seeds.

## Implementation

- Controller: `src/safe_time_evrp/mpc_central/cce_mpc.py` → `CertificateCarryingEconomicMpc`
- Certificate store: `commitment_safe_mpc/certificate_store.py`
- Theory: `mpc_central/certificate_theory.py`
- Package runner: `mpc_central/final_mpc_package.py`

## Relation to prior controllers

| Controller | Role |
|------------|------|
| B1 | Reactive validated ALNS |
| M1 | Certificate-carrying ALNS (no forecast EV first-action ranking) |
| Stochastic MPC | EV argmax over counterfactuals (weak / no persistent store) |
| CC-E-MPC | Persistent certificate + hard feasibility + EV argmax |
| Phase 3F switching | **Superseded** (blocked beneficial charge via `min_delta≥0`) |
