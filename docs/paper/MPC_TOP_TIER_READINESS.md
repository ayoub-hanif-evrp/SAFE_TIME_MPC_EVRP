# Top-tier readiness — Commitment-Safe Stochastic MPC

**Verdict:** `not_ready_development_gate_failed`

## Gates

| Gate | Status |
|---|---|
| 1 Transactional acceptance safety | **PASS** (`tests/test_css_mpc_gates_1_to_4.py`) |
| 2 Horizon-end terminal commitment | **PASS** (module + tests + `MPC_TERMINAL_FEASIBILITY_VALIDATION.md`) |
| 3 RF theorem ↔ algorithm correspondence | **PASS** (nominal, conditional; loss status explicit) |
| 4 Formulation honesty | **PASS** (candidate-set SMPC documented) |
| 5 Consistent EV energy / infinite-battery replay | **PASS** (0 `replay:travel_energy` on rebuilt arcs) |
| 6 Development advantage vs greedy-nominal | **FAIL** (completed Δ=−1.0; econ Δ≈−6.7) |
| 7 Confirmatory | **WITHHELD** |

## Development snapshot

| Controller | Mean completed (n=18) | Economic mean | Overruns |
|---|---:|---:|---:|
| B1 | 3.33 | −645 | 0 |
| M1 | 4.44 | −179 | 0 |
| Greedy-nominal CC-E | **5.50** | **156** | 13 |
| Stochastic CCE causal | 5.44 | 260 | 238 |
| **CSS-MPC (proposed)** | 4.50 | 149 | 273 |
| CSS no-forecast | 4.11 | −64 | 215 |
| CSS no-terminal | 5.06 | 90 | 235 |

Source: `docs/experiments/MPC_DEVELOPMENT_COMPARISON.json`.

## Required before claiming readiness

1. Credible paired win vs greedy-nominal on completed **or** large positive mean economic delta without large completed loss.
2. Overrun reduction (warm-start / scenario allocation / interruptible search) under matched budgets.
3. EV ablation showing battery/charge mechanism drives the gain.
4. Only then: frozen method + independent confirmatory.
