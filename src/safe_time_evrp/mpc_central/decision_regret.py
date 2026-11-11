"""Decision-regret gate: quality under equal computation, not mere action divergence.

References
----------
1. reactive — expected value using only the no-future scenario ranking (forecast-blind).
2. uniform_rollout — allocate scenario evaluations evenly across candidate first actions.
3. adaptive_mpc — allocate extra evaluations to actions whose ranking is still uncertain.

Exact reference (tiny forks only)
---------------------------------
Exhaustive evaluation of every candidate first action on every scenario via the
FleetSimulator causal plant score. Labeled as an *exhaustive first-action ranking
under causal reactive recourse* — not a full multistage open-loop DP oracle.

GO requires lower decision regret and/or better incumbent value at matched eval budget
versus uniform rollout — not merely a different chosen action.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.mpc_central.causal_plant import evaluate_action_scenario, expected_action_value
from safe_time_evrp.mpc_central.forks import ForkSpec, all_forks


@dataclass
class EvalBudgetResult:
    policy: str
    action: str
    estimated_value: float
    true_value: float
    regret: float
    scenario_evals: int
    notes: tuple[str, ...]


def exhaustive_action_values(spec: ForkSpec) -> dict[str, float]:
    """Full expected values for all candidates (exact on these tiny scenario sets)."""
    out: dict[str, float] = {}
    for action in spec.candidate_actions:
        exp, _ = expected_action_value(spec, action)
        out[action] = exp
    return out


def reactive_policy(spec: ForkSpec, truth: dict[str, float]) -> EvalBudgetResult:
    """Rank actions by the empty-future scenario only; score regret vs exhaustive truth."""
    scored: list[tuple[float, str]] = []
    evals = 0
    for action in spec.candidate_actions:
        sc = evaluate_action_scenario(spec, action, spec.scenarios[0], scenario_index=0)
        evals += 1
        scored.append((sc.value, action))
    action = max(scored, key=lambda x: (x[0], x[1]))[1]
    true_v = truth[action]
    best = max(truth.values())
    return EvalBudgetResult(
        policy="reactive",
        action=action,
        estimated_value=max(scored)[0],
        true_value=true_v,
        regret=best - true_v,
        scenario_evals=evals,
        notes=("ranked_on_omega0_only",),
    )


def uniform_rollout(spec: ForkSpec, truth: dict[str, float], *, budget: int) -> EvalBudgetResult:
    """Evenly allocate scenario evaluations across actions (cyclic over scenarios)."""
    n = len(spec.candidate_actions)
    if budget < n:
        budget = n
    sums = {a: 0.0 for a in spec.candidate_actions}
    counts = {a: 0 for a in spec.candidate_actions}
    evals = 0
    # Round-robin actions; within each action, cycle scenarios.
    while evals < budget:
        for action in spec.candidate_actions:
            if evals >= budget:
                break
            k = counts[action] % len(spec.scenarios)
            sc = evaluate_action_scenario(spec, action, spec.scenarios[k], scenario_index=k)
            # Probability-weighted running mean using known scenario probs when fully seen,
            # else uniform over sampled indices.
            sums[action] += spec.scenario_probs[k] * sc.value
            counts[action] += 1
            evals += 1
    # Normalize: if each scenario seen once, sums already expectation; if partial, reweight.
    estimates: dict[str, float] = {}
    for action in spec.candidate_actions:
        # Recompute proper expectation over unique scenario indices sampled.
        # Simpler: run full expectation when counts >= n_scenarios, else use sampled mean.
        if counts[action] >= len(spec.scenarios):
            estimates[action] = expected_action_value(spec, action)[0]
        else:
            # Use average of sampled scenario values without double-counting probs incorrectly.
            vals = []
            for i in range(counts[action]):
                k = i % len(spec.scenarios)
                vals.append(evaluate_action_scenario(spec, action, spec.scenarios[k], scenario_index=k).value)
            # These re-evals are diagnostic-only for estimate; count them? No — already paid.
            # Use stored approach instead: approximate with equal weight on sampled ks.
            sampled = [i % len(spec.scenarios) for i in range(counts[action])]
            uniq = []
            seen = set()
            for k in sampled:
                if k not in seen:
                    uniq.append(k)
                    seen.add(k)
            mass = sum(spec.scenario_probs[k] for k in uniq) or 1.0
            est = 0.0
            for k in uniq:
                est += (spec.scenario_probs[k] / mass) * evaluate_action_scenario(
                    spec, action, spec.scenarios[k], scenario_index=k
                ).value
            estimates[action] = est
            del vals
    action = max(estimates, key=lambda a: (estimates[a], a))
    best = max(truth.values())
    return EvalBudgetResult(
        policy="uniform_rollout",
        action=action,
        estimated_value=estimates[action],
        true_value=truth[action],
        regret=best - truth[action],
        scenario_evals=evals,
        notes=(f"budget={budget}",),
    )


def adaptive_mpc(spec: ForkSpec, truth: dict[str, float], *, budget: int) -> EvalBudgetResult:
    """Decision-focused allocation: explore uncertain action rankings first.

    Hypothesis: under tight budgets, focusing evals on near-ties recovers the
    exhaustive-best action more often / with lower regret than uniform allocation.
    """
    n = len(spec.candidate_actions)
    if budget < n:
        budget = n
    # Bootstrap: one eval of scenario 0 for each action.
    samples: dict[str, list[float]] = {a: [] for a in spec.candidate_actions}
    evals = 0
    for action in spec.candidate_actions:
        sc = evaluate_action_scenario(spec, action, spec.scenarios[0], scenario_index=0)
        samples[action].append(sc.value)
        evals += 1

    def estimate(action: str) -> float:
        # Fill missing scenarios with pessimistic/neutral prior = scenario0 value.
        by_k = {0: samples[action][0]} if samples[action] else {}
        # Additional samples cycle scenarios 1..
        for i, val in enumerate(samples[action][1:], start=1):
            by_k[i % len(spec.scenarios)] = val
        est = 0.0
        for k, p in enumerate(spec.scenario_probs):
            est += p * by_k.get(k, samples[action][0])
        return est

    while evals < budget:
        ests = {a: estimate(a) for a in spec.candidate_actions}
        ranked = sorted(ests, key=lambda a: (ests[a], a), reverse=True)
        # Allocate to the top-2 gap (uncertainty about the leader).
        a0, a1 = ranked[0], ranked[1] if len(ranked) > 1 else ranked[0]
        # Prefer evaluating the under-sampled scenario index for the challenger/leader.
        target = a1 if len(samples[a1]) <= len(samples[a0]) else a0
        k = len(samples[target]) % len(spec.scenarios)
        sc = evaluate_action_scenario(spec, target, spec.scenarios[k], scenario_index=k)
        samples[target].append(sc.value)
        evals += 1
        del a0  # silence lint about unused after assignment intent

    ests = {a: estimate(a) for a in spec.candidate_actions}
    # When budget allows full coverage, prefer exact expectation for the incumbent ranking.
    if evals >= n * len(spec.scenarios):
        ests = exhaustive_action_values(spec)
    action = max(ests, key=lambda a: (ests[a], a))
    best = max(truth.values())
    return EvalBudgetResult(
        policy="adaptive_mpc",
        action=action,
        estimated_value=ests[action],
        true_value=truth[action],
        regret=best - truth[action],
        scenario_evals=evals,
        notes=(f"budget={budget}", "decision_focused_allocation"),
    )


def run_decision_regret_gate(*, budgets: tuple[int, ...] = (2, 4, 6)) -> dict:
    rows = []
    for spec in all_forks():
        truth = exhaustive_action_values(spec)
        best_action = max(truth, key=lambda a: (truth[a], a))
        reactive = reactive_policy(spec, truth)
        rows.append(
            {
                "case_id": spec.case_id,
                "policy": reactive.policy,
                "budget": reactive.scenario_evals,
                "action": reactive.action,
                "true_value": reactive.true_value,
                "regret": reactive.regret,
                "best_action": best_action,
                "best_value": truth[best_action],
            }
        )
        for b in budgets:
            # Ensure budget at least n_actions
            b_eff = max(b, len(spec.candidate_actions))
            uni = uniform_rollout(spec, truth, budget=b_eff)
            ada = adaptive_mpc(spec, truth, budget=b_eff)
            for res in (uni, ada):
                rows.append(
                    {
                        "case_id": spec.case_id,
                        "policy": res.policy,
                        "budget": res.scenario_evals,
                        "action": res.action,
                        "true_value": res.true_value,
                        "regret": res.regret,
                        "best_action": best_action,
                        "best_value": truth[best_action],
                        "estimated_value": res.estimated_value,
                    }
                )

    # Compare adaptive vs uniform at each matched budget.
    comparisons = []
    by_key: dict[tuple, dict] = {}
    for row in rows:
        if row["policy"] in {"uniform_rollout", "adaptive_mpc"}:
            by_key[(row["case_id"], row["budget"], row["policy"])] = row
    case_budgets = {(c, b) for (c, b, _) in by_key}
    adaptive_better = 0
    adaptive_worse = 0
    ties = 0
    for case_id, budget in sorted(case_budgets):
        u = by_key.get((case_id, budget, "uniform_rollout"))
        a = by_key.get((case_id, budget, "adaptive_mpc"))
        if not u or not a:
            continue
        # Lower regret is better; tie-break on true_value.
        if a["regret"] + 1e-9 < u["regret"]:
            winner = "adaptive_mpc"
            adaptive_better += 1
        elif u["regret"] + 1e-9 < a["regret"]:
            winner = "uniform_rollout"
            adaptive_worse += 1
        else:
            winner = "tie"
            ties += 1
        comparisons.append(
            {
                "case_id": case_id,
                "budget": budget,
                "uniform_action": u["action"],
                "adaptive_action": a["action"],
                "uniform_regret": u["regret"],
                "adaptive_regret": a["regret"],
                "winner": winner,
            }
        )

    # Prototype GO is conditional: tiny forks only; not a publication claim.
    if adaptive_better > 0 and adaptive_worse == 0:
        verdict = "GO_PROTOTYPE"
        reason = (
            "Adaptive decision-focused allocation strictly reduces first-action regret vs uniform "
            "on at least one matched budget cell and never worsens it on these tiny plant forks. "
            "Not yet a large-scale or prior-art-differentiated paper claim."
        )
    elif adaptive_better > adaptive_worse:
        verdict = "REVISE"
        reason = "Adaptive helps on some budgets/cases but not consistently; mechanism needs sharpening."
    elif adaptive_better == 0 and ties == len(comparisons):
        verdict = "REVISE"
        reason = "No MPC-specific regret improvement vs uniform rollout at matched budgets on these forks."
    else:
        verdict = "NO-GO"
        reason = "Adaptive allocation does not improve decision regret vs uniform rollout."

    return {
        "verdict": verdict,
        "reason": reason,
        "reference_label": "exhaustive_first_action_ranking_under_causal_reactive_recourse",
        "n_comparisons": len(comparisons),
        "adaptive_better": adaptive_better,
        "adaptive_worse": adaptive_worse,
        "ties": ties,
        "truth_tables": {spec.case_id: exhaustive_action_values(spec) for spec in all_forks()},
        "rows": rows,
        "comparisons": comparisons,
    }
