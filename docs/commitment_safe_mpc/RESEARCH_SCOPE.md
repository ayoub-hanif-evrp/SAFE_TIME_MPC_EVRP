# Research scope — Commitment-Safe / Computation-Aware MPC for D-EVRP

**Main repository:** `SAFE_TIME_MPC_EVRP`  
**Branch:** `research/decision-relevant-dual-mpc`  
**Reference engineering:** `MPC_EVRP` (ALNS / simulator patterns only; no wholesale merge)

## Non-negotiable objective

**Computation-Aware, Commitment-Safe Model Predictive Control for Dynamic Electric Vehicle Routing.**

Central question: how can an electric delivery fleet make high-quality irreversible routing and customer-acceptance decisions under dynamic requests, battery/charging constraints, and limited optimization time, while guaranteeing feasibility of previously accepted commitments under an explicitly stated uncertainty model?

Research hypothesis (not yet claimed): an **anytime, certificate-carrying MPC** that reuses/updates EVRP-specific feasibility information across replans can improve the quality of executable actions before a computation deadline relative to strong reactive ALNS–MPC and full-validation safe MPC.

## What this cycle is

| Keep / freeze as optional artifact | Main trajectory |
|------------------------------------|-----------------|
| Dual-control toys, DRUB/REUB/OTUB, quarantined TEI, A/C/S trees, VoI-bound invention | Authoritative D-EVRP plant → strong ALNS–MPC baseline → full-validation safe MPC → incremental certificates → matched experiments |

Previous negative results (toy pruning screens, invalid TEI, degenerate 8×9.75 suite) are preserved, not rewritten.

## Execution milestones

1. **Phase A (current):** green CI; D1–D4 policy-class alignment + diagnostic table.
2. **Phase B:** one authoritative event-driven fleet simulator + independent replay.
3. **Phase C:** strong reactive ALNS–MPC (B0) via tested adapter to `MPC_EVRP` machinery.
4. **Phase D–E:** full-validation safe MPC (B1) and incremental certificate-carrying MPC (M1).
5. **Phase F:** exact small checks + matched development experiments; scientific verdict.

## Companion documents

| File | Role |
|------|------|
| `PHYSICAL_CONTRACT.md` | Plant / observation / commitment semantics |
| `BASELINE_COMPARISON.md` | B0 / B1 / M1 protocol |
| `INCREMENTAL_CERTIFICATE_FORMULATION.md` | Certificate + update rule |
| `PROOF_AND_COUNTEREXAMPLES.md` | Props A–C and falsifiers |
| `EXPERIMENTAL_EVIDENCE.md` | Machine-readable results |
| `SCIENTIFIC_VERDICT.md` | Go / no-go for paper claim |
| `SCENARIO_DIAGNOSTICS.md` | D1–D4 table (Phase A) |

## Commands (Phase A)

```bash
ruff check src tests
ruff format --check src tests
python -m pytest -q
python -m safe_time_evrp.dr_dual.generic.scenario_diagnostics
```
