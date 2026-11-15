# MPC failure mechanism audit

**Reference SHA:** `95706217848cdaafb4a642ece50599a3f7c9d64c`  
**Scope:** Why forecast / predictive controllers lose to greedy-nominal CC-E-MPC on development Schneider-v2 episodes.  
**Rule:** Evidence from code and recorded traces only. No new performance claims.

---

## 0. Recorded development outcomes

| Controller | Mean completed (n=18) | Source |
|---|---:|---|
| Greedy-nominal CC-E-MPC | 6.67 | `docs/experiments/INDEPENDENT_CONFIRMATORY_RESULTS.md` |
| BAP | 5.61 | same |
| Decision-Focused BAP | 5.00 | same |
| M1 | 4.89 | same |
| B1 | 3.89 | same |

DF-BAP vs greedy-nominal paired tally: **better=0, worse=5, tie=13** (`completed_delta` mean ≈ −1.67). Stage 6 confirmatory withheld.

Equal-causal forecast audit (earlier protocol): calibrated vs empty-future mean delta ≈ −0.56, tally 7/7/4 — **negligible decision value** once the objective is matched (`docs/experiments/FORECAST_SCORING_CAUSAL_AUDIT.md`).

Restricted hindsight on the same candidate set improves on greedy-nominal in **11/18** epochs (`docs/experiments/PREDICTIVE_OPPORTUNITY_AND_ACTION_AUDIT.md`). Opportunity exists offline; online ranking fails.

---

## 1. What the “predictive MPC” currently optimizes

### 1.1 Two unequal scoring laws share one class

`CertificateCarryingEconomicMpc` (`src/safe_time_evrp/mpc_central/cce_mpc.py`) branches on `scoring_mode`:

| Mode | Code path | Objective |
|---|---|---|
| `greedy_nominal` | `scenario_rollout.greedy_nominal_value` | `100 * |served| − distance` on a **nominal continuation**, **no** scenario rollouts, **no** AU penalty |
| `causal` | `scenario_rollout.expected_rollout_value` → `rollout_candidate` | `SERVICE_REWARD * completed − UNFULFILLED_PENALTY * AU − DISTANCE_PENALTY * dist` under B1-validated scenario forks |

Evidence:

```474:543:src/safe_time_evrp/mpc_central/scenario_rollout.py
def greedy_nominal_value(...):
    value = (100.0 * len(rep.served) - rep.distance) if rep.ok else -1e9
    ...
def expected_rollout_value(..., scoring_mode: str = "causal", ...):
    if scoring_mode == "greedy_nominal":
        return greedy_nominal_value(...)
```

Plant constants (`causal_plant.py`): `SERVICE_REWARD=100`, `UNFULFILLED_PENALTY=250`, `DISTANCE_PENALTY=1`.

**Failure mechanism F1 (unequal objective).** Development comparisons treat greedy-nominal as the strong baseline, but predictive variants score with causal rollouts. FORECAST_SCORING_CAUSAL_AUDIT already labels the large greedy_nominal gap an **unequal-objective artifact**. Any claim that “forecasts hurt” must separate this from true forecast value.

### 1.2 Candidate generation is not a finite-horizon stochastic program

At each epoch, CCE:

1. Advances / revalidates a certificate.
2. Calls `generate_counterfactual_actions` (ALNS + heuristics).
3. Hard-filters with `validate_continuation`.
4. Scores survivors with `expected_rollout_value`.
5. Executes the **entire** selected route plan’s first plant action via `Decision.routes` (receding only in the event loop, not as an explicit multi-stage recourse tree).

There is **no** explicit nonanticipative multi-stage decision tree, no terminal value function beyond residual B1 recourse inside rollouts, and no joint optimization of accept/reject + charge + sequence as one mathematical program. Forecasts enter only as **scenario scoring of pre-generated first actions**.

**Failure mechanism F2 (action-set / ranking architecture).** Predictive “MPC” is argmax over a small discrete first-action catalogue, not a solved stochastic MPC. If the catalogue omits the beneficial charge/wait/reposition, no forecast can recover it.

---

## 2. Counterexample traces: forecast selects worse physical actions

### 2.1 Causal empty vs calibrated — first-action disagreement

From `docs/experiments/forecast_scoring_causal_results.json` → `action_audits`:

**Episode `c101C5` realization 0, t=0, trigger=`request_release`, open=`C64`:**

| Scorer | First leg |
|---|---|
| Causal empty-future (`use_forecast=0`) | `v1 → S0` **charge** |
| Conditional calibrated (`use_forecast=1`) | `v1 → D0` **reload** |

Same public state; forecast path avoids immediate charging. Later closed-loop service suffers when energy/time slack is needed.

**Episode `c101C5` realization 1, t=0, open=`C12`:**

| Scorer | First leg |
|---|---|
| Empty-future | `v1 → S0` charge |
| Calibrated | `v1` **idle** |

**Failure mechanism F3 (myopic forecast distraction).** Scenario customers inflate expected future service value of “keep flexibility / stay at depot / idle” relative to securing energy for the **already announced** request. With only `n_scenarios=2` and (historically) inflated catalogue sizes (`n_forecast_customers_sc0: 32` on a 5-customer stem in the same audit JSON), the estimator is high-variance and biased toward phantom futures.

Finite-demand repair reduced overprediction intensity, but Stage 2–7 DF-BAP still lost 0–5–13 — calibration alone did not fix ranking.

### 2.2 BAP wall-clock divergence (inspected `c208C15`)

`docs/experiments/BAP_C208C15_DIVERGENCE_AUDIT.md`:

- Iteration-primary zero-override **matches** greedy-nominal (15 completed).
- Cooperative 0.35s wall: greedy-nominal 15 completed vs BAP-allow-override **13** completed (2 rejects).

**Failure mechanism F4 (budgeted override under cooperative ALNS).** Speculative scenario scoring consumes the same wall as incumbent generation. Overrides that look good under noisy rollouts reject customers the incumbent would have kept. This is not an MPC theorem failure; it is a compute-allocation and misspecified-advantage failure.

---

## 3. Horizon truncation, terminal penalties, charging

| Item | Implemented? | Effect |
|---|---|---|
| Prediction horizon `H` | Yes (`horizon` on episode / controller) | Forecasts clipped; no certified **terminal set** beyond “B1 can finish the fork” |
| Soft AU penalty in causal score | Yes (`UNFULFILLED_PENALTY=250`) | Present in causal path; **absent** in greedy_nominal |
| Terminal value / feasible suffix constraint | Only certificate coverage at emit time | Obligations past `H` can be “planned” in routes but not protected by a recursive terminal set in the stochastic program |
| Predictive charging | Only if charge appears in counterfactual catalogue and wins argmax | No explicit energy-to-serve-future term |

**Failure mechanism F5 (missing commitment terminal constraint in the stochastic problem).** Hard feasibility is checked **now** via `validate_continuation`. The stochastic score does not enforce a terminal feasible set that preserves accepted obligations under every scenario beyond the prediction horizon. Horizon truncation can therefore hide delayed infeasibility that greedy nominal continuations happen to avoid by serving aggressively.

---

## 4. Treatment of accepted obligations in predicted scenarios

In causal rollouts (`scenario_rollout.seed_simulator_from_observation` + `B1ValidatedRecourse`):

- Public accepted customers are restored as `ACCEPTED`.
- Future synthetic announcements may be accepted/rejected by recourse.
- Existing obligations are **not** optional rewards in the plant; AU incurs −250.

However, **candidate generation** still proposes new accepts based on ALNS heuristics. Scenario scoring can prefer a first action that rejects a newly announced customer to chase forecasted synthetics, while the greedy-nominal score prefers covering more of the **current** continuation set (`100*|served|`).

**Failure mechanism F6 (obligation vs optionality mismatch across modes).** Causal scenarios treat future accepts as soft expected reward; greedy-nominal maximizes immediate certified coverage. Without a shared economic objective, “better forecasts” systematically disagree with the strongest baseline.

---

## 5. Invalid infinite-battery experiment (`replay:travel_energy`)

### Evidence

Stage 4 rows in `INDEPENDENT_CONFIRMATORY_RESULTS.json` mark `"infinite_battery": true` with many `"failure": "replay:travel_energy"`.

### Root cause (reproduced)

`_infinite_battery` in `stage2_to_7_eval.py` only replaces `VehicleType` (`consumption_rate=0`, huge battery) via `dataclasses.replace`. **Arc energies stay at the original `r * distance`.**

- Simulator / `NominalLinearEnergy.travel_energy` logs **`arc.energy`** (still > 0).
- Independent replay `_expected_energy` recomputes **`consumption_rate * hypot(...)`** → **0**.
- Mismatch → `ReplayRejection("travel_energy", ...)`.

Reproduction on `c101C5`: broken replace → `ok=False, code=travel_energy`; rebuilding arcs with `energy=0` → `ok=True`.

**Failure mechanism F7 (ablation instrumentation bug).** The infinite-battery cell does not relax energy consistently across plant and validator. EV-specific conclusions from that cell are invalid until arcs (or the energy model) are rebuilt coherently.

---

## 6. Decision-budget overruns (186)

From Stage 5 latency summary (DF-BAP):

- `deadline_overruns_sum`: **186** across 18 episodes.
- Greedy-nominal: **16**.

Overruns increment in `_emit` when `elapsed > time_limit_seconds` (`cce_mpc.py` ≈ lines 217–219; same pattern in BAP wrappers). Scoring loop also breaks on cooperative deadline (`cooperative_deadline_hit_during_scoring`).

Interpretation:

- Overruns count **cooperative wall exceedances**, not hard preemption.
- DF-BAP adds screening + paired confirm rollouts → more work per epoch → more overruns.
- ALNS is not reliably interruptible; “anytime” means “stop proposing and emit incumbent,” not hard real-time.

**Failure mechanism F8 (compute starvation of the incumbent-quality path).** Extra predictive work burns the budget that greedy-nominal spends on improving the certified continuation.

---

## 7. Information leakage check

| Boundary | Status |
|---|---|
| `make_public_snapshot` / `sanitize_instance` | Drops unreleased customers; filters arcs; metadata allowlist (`public_snapshot.py`) |
| `Observation.public_customer_count` | Public `N` only; identities/coords of unreleased customers hidden (`PUBLIC_INFORMATION_CONTRACT.md`) |
| Forecast synthetics | `syn_*` train atoms; quarantine on eval instance (`test_mpc_central_forecast_safety.py`) |
| Scenario fork seeding | Reconstructs only public releases; hidden customers absent (`scenario_rollout.py` docstring) |

No evidence in the audited paths that online decide() reads unreleased customer attributes. Residual risk: holding the full `Instance` on the controller object — mitigated by mandatory public snapshot for validation/planning copies.

---

## 8. Ranked root causes (evidence strength)

| Rank | Mechanism | Strength |
|---:|---|---|
| 1 | F1 Unequal objective (greedy_nominal vs causal) | **Strong** — quantified in FORECAST_SCORING_CAUSAL_AUDIT |
| 2 | F2 Discrete first-action catalogue ≠ stochastic MPC solve | **Strong** — code structure |
| 3 | F3 Forecast-driven wrong first legs (charge→reload/idle) | **Strong** — action_audits traces |
| 4 | F8 Predictive compute displaces incumbent search | **Strong** — 186 vs 16 overruns; BAP wall divergence |
| 5 | F5 No recursive terminal commitment set in the stochastic program | **Medium** — architectural gap vs theorem needs |
| 6 | F6 Soft future service vs hard current coverage mismatch | **Medium** — follows from F1+F5 |
| 7 | F7 Infinite-battery replay bug | **Strong** (instrumentation); blocks EV ablation validity |
| 8 | F4 Noisy override under misspecified advantage | **Medium** — c208C15 wall cell |

---

## 9. Implications for the proposed Commitment-Safe Stochastic MPC

Do **not** add another heuristic wrapper (BAP / DF-BAP style). Required repairs before claiming MPC progress:

1. **One economic objective** for proposed method and fair ablations (plant weights fixed).
2. **Explicit finite-horizon stochastic problem** with nonanticipativity, first-action execution, and re-solve.
3. **Commitment terminal constraint / certified suffix** beyond the prediction horizon.
4. **Consistent energy model** for plant, optimizer, and replay (fix infinite-battery arcs).
5. **Incumbent-first compute schedule** with profiled latency; no hard real-time claims.
6. Preserve B1, M1, greedy-nominal, and existing stochastic MPC as baselines only.

Hindsight opportunity (11/18) justifies continued research; current online predictive policies are **not** empirically competitive under the recorded protocol.
