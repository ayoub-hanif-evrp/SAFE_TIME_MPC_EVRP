# Action-causality gate (Phase 3)

**Verdict: REVISE**

Prediction / scenario information **does** change executable first actions versus a forecast-blind reactive rule on both microscopic forks. On these forks, the Phase-3 “commitment-safe MPC” stand-in **coincides with standard stochastic rollout** (same objective over the same safe action set). That is necessary causality evidence for predictive MPC, **not** evidence of a differentiated MPC mechanism beyond ordinary rollout.

Artifact: `docs/mpc_central/action_causality_gate.json`  
Code: `src/safe_time_evrp/mpc_central/forks.py`, `first_action_eval.py`  
Tests: `tests/test_mpc_central_causality.py`

## Policies compared (identical candidate sets)

| Policy | Rule |
|--------|------|
| Reactive | Maximize value on the **no-future** scenario only |
| Stochastic rollout | Maximize expected causal recourse over scenarios |
| Commitment-safe MPC (Phase-3 stand-in) | Same expectation among first actions with a feasible nominal prefix |

No clairvoyance: scenario customers are optional only inside planning; windows/releases constrain recourse via `evaluate_route`.

## Case A — Predictive charging fork

**Present actions:** `serve_near` vs `charge_first`  
**Uncertainty:** Far customer absent (p=0.35) vs announced at t=1 (p=0.65)

| Action | Reactive value (ω0) | Stochastic expectation |
|--------|---------------------|-------------------------|
| serve_near | **88.0** | 88.0 |
| charge_first | 80.65 | **136.67** |

| Policy | Chosen action |
|--------|---------------|
| Reactive | `serve_near` |
| Stochastic rollout | `charge_first` |
| Commitment-safe MPC | `charge_first` |

**Mechanism:** Serving Near first still allows depot return, but subsequent charging makes Far miss its due. Charging first preserves a feasible Near+Far continuation. Forecast weight on Far flips the first action.

## Case B — Irreversible admission fork

**Present actions:** `accept_now` vs `reject_now`  
**Uncertainty:** Future absent (p=0.2) vs announced at t=5 (p=0.8)

| Action | Reactive value (ω0) | Stochastic expectation |
|--------|---------------------|-------------------------|
| accept_now | **60.0** | 60.0 |
| reject_now | 0.0 | **75.2** |

| Policy | Chosen action |
|--------|---------------|
| Reactive | `accept_now` |
| Stochastic rollout | `reject_now` |
| Commitment-safe MPC | `reject_now` |

**Mechanism:** Accepting/serving costly Now consumes the time needed for Future’s tight window. Prediction makes rejection the better first decision.

## Gate checklist

| Research gate | Result |
|---------------|--------|
| Horizon/forecast changes executable first actions | **Pass** (2/2 forks) |
| Shared first action + causal scenario recourse | **Pass** (enumerator) |
| Proposed rule ≠ standard stochastic rollout | **Fail** on these forks |
| General superiority / paper claim | **Not claimed** (hand-designed forks only) |

## Scientific reading

1. The repository **can** host a genuine predictive MPC question: first actions move when futures are valued.  
2. Gate 3C’s failure mode is **not** repeated for reactive-vs-prediction — prediction matters here.  
3. Gate 3C’s second failure mode **is** repeated for novelty: without a new decision/compute mechanism, “MPC” collapses to standard stochastic rollout.  
4. **Next justified step (Phase 4–5, only if pursued):** implement a plant-facing predictive controller **and** a *decision-focused computational allocation* (or another clearly differentiated rule), then re-run causality against matched rollout under the same budget. If it still ties rollout, stop and revise the hypothesis.

## Stop rules triggered

- Do **not** scale Schneider/Amazon holdouts on this gate alone.  
- Do **not** call ALNS improvements an MPC contribution.  
- Do **not** treat Phase-3 forks as empirical proof of closed-loop dominance.
