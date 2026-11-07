# Prior-art confrontation

| Method | Learns | Action→info? | Fleet share | TW | Irrevocable accept | Adaptive charge | Hard safety | RH MPC | Solver latency | Core result |
|--------|--------|--------------|-------------|----|--------------------|-----------------|-------------|--------|----------------|-------------|
| Åkerblom et al. 2023 | Road-segment energy (Bayesian) | Yes (path choice) | Yes (sync multi-agent) | No | No | No (navigation) | Battery via energy | Bandit/online learning | No | Regret bounds for TS/UCB EV navigation |
| Hewing et al. 2020 (LB-MPC survey) | Dynamics / disturbance models | Sometimes | N/A | Rarely EVRP | Constraint tube/backup | Possible | Often yes (sets) | Yes | Discussed | Safe learning-MPC taxonomy |
| Jiang et al. 2026 | Stochastic requests (+ EV ops) | Via scenarios | Fleet routing | Yes | Dynamic accept | Proactive charge | Model-dep. | Lookahead / RL | Limited | Stochastic dynamic EVRP |
| Basso et al. (safe RL EVRP) | Policy / risk | Indirect | Fleet | Yes | Soft/hard variants | Yes | Safe RL constraints | RL | — | Safe RL for stochastic EVRP |
| Zhang et al. 2023 | Request value-to-go | No energy dual | Multi-vehicle | Yes | Accept/assign | No EV focus | — | Online scheduling | Emphasized | Knapsack ADP opportunity cost |
| Jeong et al. 2024 | Energy uncertainty for charging | Limited | — | — | — | Robust adaptive charge | Robust | — | — | Adaptive robust charging |
| Gräfe & Trimpe 2025 | — | — | — | — | — | — | — | Computation-aware MPC | Yes | Latency-aware MPC |
| **This work (toy)** | Shared \(\theta\) energy factor | Yes (corridor choice) | Shared belief (designed; multi-EV not exact-solved) | Yes (toy dues) | Yes (A commitment) | Yes (charge vs C) | Set-support backup | Exact tree / minimal RH | Not yet | **Phenomenon only**; no new theorem |

## Precise difference vs Åkerblom

Åkerblom: learn edge energies to navigate OD pairs with battery limits and regret guarantees.  
**Not claimed new here:** Bayesian energy learning, multi-agent sharing, exploration for energy.

**EVRP coupling studied here:** irrevocable time-window commitments + charging duration tradeoffs under a shared latent energy factor, with a **safe** dual first action that differs from safe passive learning on an exact tree.

## Precise difference vs safe learning MPC

Safe LB-MPC: keep state in a tube / backup set while learning.  
Our toy safety filter is an instance of that idea on discrete \(\theta\)-support for customer commitments. **Not claimed new:** “only explore if a backup remains feasible.”

## Conclusion of confrontation

No published paper found that **exactly** packages EVRP commitments + charging + shared energy dual control with an exact Bayes-adaptive delivery oracle. However, the **computational mechanism we implemented reduces to known constrained dual / safe learning-MPC logic**. Problem novelty ≠ theorem novelty.
