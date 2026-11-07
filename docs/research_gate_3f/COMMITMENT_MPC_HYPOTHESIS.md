# Gate 3F — Commitment-MPC research hypothesis (specification only)

## Proposed question

Can a computationally tractable stochastic MPC policy quantify the **future cost of accepting an irreversible EV delivery obligation**, while preserving certified feasibility of existing obligations under energy and travel-time uncertainty?

## Information

At decision epoch τ, the controller observes plant `Observation` (released/accepted/completed/rejected/in-service, vehicle anchors/locks) and may use train-only anonymous demand forecasts. It must not read unreleased evaluation identities.

## Decision object

Irreversible **admission** (accept/reject/defer) and **charging / routing** suffixes executed under `FleetSimulator` noninterruptibility.

## Objective sketch

Minimize expected routing cost + λ rejection cost + ρ commitment-violation / recourse cost, subject to an explicitly defined commitment-feasibility condition (nominal now; budgeted robust as an intermediate; certified set-invariance only if proved later).

## Closest priors (why a terminal alone is insufficient)

Stochastic dynamic EVRP, ADP value approximations, scenario lookahead, and robust EV routing already cover charging-aware anticipatory decisions. A shadow price or flexibility-style terminal on the same constructive candidate set (Gate 3C–3E negative result) is **not** a differentiated claim.

## What would count as nontrivial

One of:

1. An EVRP-structured **sound bound** on the future cost of a commitment with a proved guarantee relative to a known method, or
2. A **certified approximation** with a measurable commitment–service–computation frontier advantage against strong stochastic baselines under the Gate 3F testbed, or
3. A complexity / representation result for contingent future actions that established scenario trees do not already provide at the same fidelity.

## Tiny counterexample sketch (not implemented)

Instance where accepting near customer A is myopically cheap but eliminates the only energy-feasible continuation for a soon-to-arrive clustered request B that a commitment-cost policy would defer A to protect — while deterministic prefix rollout (same candidates, distance+service score) accepts A. Requires multi-scenario nonanticipative evaluation, not single-scenario insertion.

## Stop rule

Do **not** implement another terminal heuristic or start Part 3 until one of the nontrivial criteria above is chosen and stated as the paper claim.
