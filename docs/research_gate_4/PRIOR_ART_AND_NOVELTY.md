# Gate 4 — Prior Art and Novelty Audit

## Closest competitors

| Paper | Contribution | Threat |
|-------|--------------|--------|
| Zhang et al., EJOR 2023 ([doi](https://doi.org/10.1016/j.ejor.2022.07.015)) | Knapsack residual-time approximations of expected reward-to-go for accepting stochastic requests; online acceptance rules | Marginal opportunity cost of admission is already established ADP practice |
| Jiang, Zhang & Puchinger, Transportation Science 2026 ([doi](https://doi.org/10.1287/trsc.2025.0476)) | Dynamic EVRP with stochastic requests, proactive charging, perfect-information rollout, DQN | Stochastic lookahead + EV charging already a direct competitor |
| Sivagnanam et al., ICCPS 2026 ([doi](https://doi.org/10.1109/ICCPS68698.2026.00012)) | Prompt confirmation, preserved commitments, continual reoptimization, non-myopic value | Certified acceptance + anytime improvement not automatically novel |
| Han et al., TRE 2025 ([doi](https://doi.org/10.1016/j.tre.2025.104211)) | Related dynamic/electric routing literature | Raises bar for EV-specific claims |
| Jeong et al., TRC 2024 ([doi](https://doi.org/10.1016/j.trc.2024.104529)) | Related dynamic routing under uncertainty | Scenario / lookahead baselines already strong |

## What would still be new

A **sound, EVRP-specific certificate or bound** on marginal commitment cost \(\Delta_r\) that is:

- not reducible to knapsack residual-time ADP (Zhang),
- not reducible to scenario rollout / VFA (Jiang et al.),
- not merely “preserve accepted customers while reoptimizing” (Sivagnanam),
- with a quantified approximation/conservatism guarantee useful inside causal MPC.

## Novelty bar we refuse

Combining existing names (“commitment-preserving stochastic MPC with flexibility terminal”) without a new structural result.
