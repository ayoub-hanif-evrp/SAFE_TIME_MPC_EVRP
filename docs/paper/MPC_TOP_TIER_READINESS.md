# Top-tier readiness — Commitment-Safe Stochastic MPC

**Verdict:** `not_ready_development_gate_failed`

**Protocol:** `mpc_development_v2_full_ablations`

## Gates

| Gate | Status |
|---|---|
| 1 Transactional acceptance safety | **PASS** |
| 2 Horizon-end terminal commitment | **PASS** |
| 3 RF theorem ↔ algorithm | **PASS** (nominal) |
| 4 Formulation honesty | **PASS** |
| 5 EV energy consistency / infinite-battery replay | **PASS** |
| 6 Full ablation matrix + charge/energy + paired CIs | **PASS** (reporting complete) |
| 7 Development advantage vs greedy-nominal | **FAIL** |
| 8 Confirmatory | **WITHHELD** |

## Development snapshot (n=18, budget 0.35s)

| Controller | Completed | Economic | Charge time | Episode-mean latency |
|---|---:|---:|---:|---:|
| B1 | (see JSON) | | | |
| M1 | | | | |
| Greedy-nominal | **4.78** | −23 | 147 | 0.048 |
| Stochastic CCE | (see JSON) | | | |
| **CSS-MPC** | 4.06 | 133 | 174 | 0.136 |
| CSS no-charge | 3.22 | −56 | 117 | 0.160 |
| CSS short H | 4.39 | 220 | 171 | 0.109 |
| CSS long H | 4.11 | 144 | 187 | 0.162 |
| CSS no warm-start | 2.11 | −266 | 95 | 0.118 |

Paired CSS vs GN completed: Δ=−0.72, tally 7/8/3, 95% CI **[−2.87, 1.43]** (includes 0).  
Paired CSS vs GN economic: Δ=+156, tally 11/7/0, 95% CI **[−285, 596]** (includes 0).

## Ablation findings

| Question | Result |
|---|---|
| Forecast on vs off | See `css_vs_no_forecast` in JSON |
| Terminal on vs off | See `css_vs_no_terminal` |
| Anticipatory charging | CSS beats no-charge on completed (Δ=+0.83, 7/3/8); CI includes 0 |
| Short vs long horizon | Inconclusive (Δ=+0.28, CI includes 0) |
| Warm start | **Clear benefit** vs no warm-start (Δ=+1.94, CI **[0.70, 3.19]**, 9/0/9) |
| Infinite battery | Replay OK; CSS still not ahead of GN |

## Bottom line

Reporting checklist from the prompt is complete. The method remains **not** empirically competitive enough vs greedy-nominal for confirmatory / top-tier claims.
