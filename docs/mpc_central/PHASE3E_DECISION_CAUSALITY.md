# Phase 3E — Decision-level causal audit

**Primary decision: `GENUINE_MPC_FAILURE` (+ coexisting labels below)**

Starting commit audited: `f25a41a`. Holdout untouched. No new objective / allocation mechanism invented.

Artifacts: [`phase3e_decision_traces.json`](phase3e_decision_traces.json), [`phase3e_matched_results.json`](phase3e_matched_results.json), [`PHASE3E_BASELINE_FAIRNESS.md`](PHASE3E_BASELINE_FAIRNESS.md)

## Coexisting findings

| Label | Meaning here |
|-------|----------------|
| `EQUIVALENT_TO_STOCHASTIC_ROLLOUT` | Matched seeds → proposed ≡ stochastic on all 9 valid cells |
| `EVALUATION_ARTIFACT` | Prior `A_dense_arrivals` 8-vs-6 “win” does not survive matched seeds |
| `FIRST_ACTIONS_MATTER` | Sticky first-action interventions change plant outcomes / predicted values |
| `GENUINE_MPC_FAILURE` | Under matched resources, predictive/stochastic is worse than B1 more often than it wins |

This is **not** a scientific GO for predictive superiority. A single-seed dense gain under mismatched seeds is discarded.

## Task 1 — Fairness (summary)

See [`PHASE3E_BASELINE_FAIRNESS.md`](PHASE3E_BASELINE_FAIRNESS.md). Allocation was cosmetic; seed mismatch was the unfair lever. Fair reruns use identical seeds and budgets.

## Task 2 — Winning / losing case traces (matched seed 7)

### `A_dense_arrivals` (was “win”; matched seed → loss)

| Controller | Completed | Accepted-unfulfilled | Opt seconds | Replay |
|------------|----------:|---------------------:|------------:|--------|
| B1 | 6 | 2 | ~0.35 | ok |
| Predictive | 4 | 4 | ~2.33 | ok |

**First consequential divergence** (epoch 1, `t≈5.28`, trigger `request_release` for C5):

- **B1:** newly accepts `C5`; `v1→C5` service, `v2→D` return.
- **MPC:** accepts nothing; `v1` idle, `v2→S` charge.

So the prior dense “improvement” was not a validated matched-seed predictive choice. Under matched seed 7, the first physical fork is **serve C5 vs charge/idle**, and the episode ends worse for MPC (4 completed, 4 AU vs B1’s 6 / 2).

### `A_low_soc_charge` (loss preserved)

| Controller | Completed | AU | Replay |
|------------|----------:|---:|--------|
| B1 | 2 | 0 | ok |
| Predictive | 1 | 0 | ok |

**First consequential divergence** (epoch 2, `t≈19.45`):

- **B1:** rejects marginal `C6` while continuing `v1→C1` service.
- **MPC:** does **not** reject `C6` (same first legs otherwise; only one validated action in the audit field).

Reject discipline at low SOC is the causal fork; predictive/stochastic under-rejects relative to B1 and finishes one fewer completion.

## Task 3 — Do equal rollout values mean first actions are irrelevant?

On `B_phase_b` representative states, ALNS serve / accept / `wait_idle` can share the **same predicted mean** (~121.63). Sticky plant interventions (force first action until the next legal decision, then B1 recourse) show:

- Predicted values are **not** all identical across the full candidate set (e.g. reject / charge differ).
- Sticky outcomes differ in distance and, for some forces, replay validity.
- Verdict recorded: **`ACTIONS_MATTER`** — equal values among a subset do not license treating all first actions as physically interchangeable.

Note: sticky ALNS force can still hit `early_request_access` on replay in this probe; that is quarantined as sticky-probe noise, not used as a superiority claim.

## Task 4 — `B_easy_dynamic` replay

Previous independent replay failure for predictive variants was **`duplicate_service`**: decisions listed rejects for customers already completed / in service.

**Repair:** `sanitize_rejects` in `counterfactual_actions.py` and on the predictive controller’s emitted decision — never reject completed or in-service customers.

**After repair:** `replay_ok=true`, code `ok` (seed 7 and all matched-grid cells for this case).

## Task 5 — Small matched multi-seed evaluation

Cases: `A_dense_arrivals`, `A_low_soc_charge`, `B_easy_dynamic`. Seeds: `{3, 7, 11}` (fixed a priori; not chosen by win rate). Controllers: B1, M1, `stochastic_uniform`, `proposed_mpc`.

| Metric | Value |
|--------|------:|
| Cells / valid | 9 / 9 |
| Wins vs B1 (completed) | 1 |
| Losses vs B1 | 4 |
| Ties vs B1 | 4 |
| Stoch ≡ proposed | 9 / 9 |
| Mean proposed − B1 completed | −0.33 |

Per-cell highlights:

- Dense seed 3: tie at 8 completed (all controllers).
- Dense seed 7: proposed/stoch **lose** (−2 completed, +2 AU vs B1).
- Dense seed 11: proposed/stoch **win** (+2 completed, −2 AU vs B1) — kept as a real positive cell, not generalized.
- Low-SOC all seeds: proposed/stoch complete 1 vs B1’s 2.
- Easy all seeds: tie at 3; replay ok after reject sanitize.

Optimization time remains higher for predictive/stochastic than B1; claims of superiority still require matched computation in future mechanism work — here the matched-seed outcome is already mostly worse/tied vs B1.

## Smallest justified research decision

1. **Do not treat the repaired Phase 3D dense win as evidence of a distinct proposed MPC.** It was an `EVALUATION_ARTIFACT` under seed mismatch; under matched seeds the same development instance can lose.
2. **Label the current “proposed” controller `EQUIVALENT_TO_STOCHASTIC_ROLLOUT`.** Mechanism differentiation has not been implemented.
3. **Relative to B1 on these focus cells, the honest aggregate is `GENUINE_MPC_FAILURE` (candidate → decision):** more losses than wins under matched seeds/budgets, with all episodes replay-valid after the reject sanitize.
4. **Preserve the dense seed-11 gain and low-SOC reject fork as research leads** for a *future* distinct predictive mechanism — not as a paper GO.
5. **Holdout remains frozen.** Next methodological step (only if pursuing predictive value): design a mechanism that is *not* identical to uniform stochastic rollout, then re-audit under this same fairness contract.
