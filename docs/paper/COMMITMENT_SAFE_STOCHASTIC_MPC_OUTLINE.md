# Manuscript outline

**Working title:** Commitment-Safe Stochastic Model Predictive Control for Dynamic Electric Vehicle Routing with Time Windows

**Status:** Outline only. No performance claims for the proposed MPC until development gates pass.

## Sections

1. Introduction and precise research gap — cite Sivagnanam, Ulmer, Spinelli, classical RF-MPC; state hypothesis.
2. Dynamic EVRP system model — Schneider-derived plant, irreversible accepts, noninterruptible locks.
3. Information structure and uncertainty — public snapshot; finite-demand forecasts; no leakage.
4. Stochastic receding-horizon MPC formulation — state, decisions, economic objective, nonanticipativity.
5. Commitment-preserving terminal constraints — \(\mathcal{X}_f\), certified suffix.
6. Recursive feasibility analysis — `docs/proofs/RECURSIVE_FEASIBILITY_STOCHASTIC_MPC.md`.
7. MPC solution algorithm — warm start, ALNS subroutine, incumbent-first budget.
8. Computational complexity and runtime — cooperative walls; latency percentiles; no hard RT claim.
9. Experimental protocol — Schneider-v2 development; baselines B1/M1/greedy-nominal/stochastic; ablations.
10. Results, ablations, limitations — preserve negative historical predictive results; confirmatory only after gates.

## Baselines (fixed names)

- B1: reactive validated ALNS
- M1: certificate-carrying ALNS
- Greedy-nominal CC-E-MPC
- Existing stochastic / causal predictive MPC

## Proposed method (one name)

- Commitment-Safe Stochastic MPC (`CommitmentSafeStochasticMpc`)
