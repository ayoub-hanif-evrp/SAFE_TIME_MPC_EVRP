# Literature novelty-threat matrix (Gate 3B)

Evidence: ABS = abstract/secondary; FT = fuller read this gate / prior gates; REPO = this repository.

| Competitor class | Exemplars | Threat to “flexible feedback MPC for dynamic EVRP” | Residual opening |
| --- | --- | --- | --- |
| Static two-stage ARO EVRP | Han 2025; Jeong 2024 | Adjustable charge/start on **fixed** routes | Online acceptance + causal **routing** forks |
| Stochastic charge recourse on fixed sequences | Spinelli 2026 | Threshold charging / detours on fixed customer order | Free next-node choice after partial observation |
| Dynamic EVRP / learning | Jiang et al. 2026 DQN/lookahead; **Transportation Science DEVRP stochastic requests (2025.0476)** PIR + DQN with proactive charging | Strong online EVRP baselines with charging | Commitment certificates under residual energy uncertainty; flexibility valuation distinct from rollout/DQN reward |
| Online charging commitment (station-side) | GECCO/ACM 2026 surrogate EVCSP commitment | Irrevocable admission at chargers | Vehicle routing + service commitments, not only charger admission |
| Electric AMoD MPC | RE-AMoD MPC 2025 | Predictive matching/routing/charging | Logistics EVRP TW + accepted deliveries ≠ ride-sharing AMoD |
| Prompt / anytime dynamic VRP | Sivagnanam et al. 2026 | Commitment + compute | Not electric; no residual energy budget |
| Multistage robust / DP | Bertsimas–Sim; robust DP textbooks; FPTAS multistage | Exact feedback feasibility **is** DP | Need a **scalable approximate mechanism** with a clear reason it beats DP enumeration / RH open-loop |
| Stochastic / robust MPC | Classic EMPC, tube MPC, scenario MPC | Predictive horizons already standard | EVRP-specific commitment + charging + demand coupling |
| Anytime / insertion heuristics | Classical DVRP | Strong empirical baselines | Not predictive under energy uncertainty |
| This repo Parts 1–3A | Rectangle cert; backup; Gate 3A NO-GO | Rectangular certs / Bellman labeling are **not** novelty | Need empirical methodological win with falsifiable mechanism |

## Candidate mechanism (to falsify, not assume)

**Scalable feedback MPC that prices future routing flexibility while preserving accepted service commitments under energy uncertainty.**

Falsifiable claims:

1. On EVRP-TW-D territories with physically plausible batteries, there exist periods where **energy or charging changes accept/route decisions** vs ignore-battery baselines.
2. Relative to (a) open-loop robust RH, (b) Han-style fixed-route charge recourse, (c) myopic insertion, the flexibility-aware MPC changes **present** actions when the horizon includes future request/charge options, and those changes improve commitment feasibility or service rate on held-out territories.
3. Benefit is **not** explained by merely running exact multistage DP on a toy graph (Gate 3A already collapsed that theorem path).

If (1) fails in the feasibility pilot → **NO-GO** (no real control problem).  
If (1) holds but (2) fails vs strong baselines → **REVISE**.  
If (2) holds with a clear causal mechanism → candidate **GO** for an empirical methods paper (still no fake theorem).
