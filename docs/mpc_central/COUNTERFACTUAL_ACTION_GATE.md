# Counterfactual action gate

**Status: PASS (diversity) / FAIL (downstream value)**

## Purpose

Force the live MPC to compare **distinct executable first decisions**, not renamed solvers that share the same first leg.

## Generator (`counterfactual_actions.py`)

When feasible and commitment-safe:

- Accept vs reject a marginal announced request  
- Charge now (legal station visit) vs continue / idle  
- Wait / idle preserve  
- Assign accept to different idle vehicles  
- Commit-only (no new accepts)  
- ALNS + insertion baselines (deduped)

Canonical key: `FirstActionKey(newly_accepted, rejected, first_legs)` — first `(vehicle, node, purpose)` only.

Illegal / completed / unreleased service targets are sanitized before validation.

## Diversity results (accelerated matrix)

All six development cases produced ≥2 distinct valid commitment-safe first actions (see `accelerated_results.json` → `diversity_gate`).

## Downstream finding

Diversity is necessary but not sufficient. On the matched closed-loop pilot, the proposed MPC **did not** convert extra candidates into better completed-service outcomes vs B1. Identical-candidate stochastic rollout tied the proposed controller — so the failure is not “missing candidates” alone; the **selection/scoring rule** (and/or residual terminal value) currently prefers under-serving actions.
