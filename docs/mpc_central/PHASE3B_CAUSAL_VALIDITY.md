# Phase 3B — Causal validity

**Branch:** `research/commitment-safe-predictive-mpc`  
**Goal:** Repair scientific validity of the Phase-3 evaluator before any large predictive controller.

## Defects repaired (from review)

| Issue | Repair |
|-------|--------|
| MPC == rollout by construction | Replaced identity argmax with **independent** policies: reactive, uniform rollout, adaptive decision-focused allocation (`decision_regret.py`) |
| `_release_t` ignored | FleetSimulator causal loop: futures only via `schedule_release`; recourse is forecast-blind `EventTriggeredMPC` |
| Restricted skeletons called “exact” | Toy `first_action_eval.py` labeled **approximate / legacy**. Reference for regret is **exhaustive first-action ranking under causal reactive recourse** on the plant — not a full multistage open-loop DP |
| No plant / no commitments | Cases A–C run on `FleetSimulator` + replay; Case C has prior accepted `Must` |

## Causal plant contract

Module: `src/safe_time_evrp/mpc_central/causal_plant.py`

1. Shared first `Decision` applied once.  
2. Scenario customers appear only at release events.  
3. Recourse never receives unreleased IDs in the observation.  
4. Adversarial test: a clairvoyant first route toward a hidden customer is detectable (`clairvoyant_route_would_leak`).  
5. Causal recourse test: `early_service_before_release` is empty for legal policies.  
6. Prior commitments: illegal payload / uncoverable accepts score as catastrophic failure (Case C `accept_now`).

## Microscopic plant results (expected completed value)

| Case | Best predictive action | Reactive-ranked action | Notes |
|------|------------------------|------------------------|-------|
| A charging | `charge_first` (165) | `serve_near` (100) | Far missed after serving Near first |
| B admission | `reject_now` (160) | `accept_now` (100) | FutureA+B only if Now rejected |
| C commitment | `serve_must` / `reject_now` (170) | — | `accept_now` infeasible (payload); Must preserved |

## Legacy toy gate

`ACTION_CAUSALITY_GATE.md` / `first_action_eval.py` remain as the Phase-3 prototype record (REVISE: MPC≡rollout by construction). **Do not** use that file as the Phase-3B scientific gate.
