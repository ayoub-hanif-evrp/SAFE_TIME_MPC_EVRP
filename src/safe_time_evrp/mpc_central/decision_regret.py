"""Decision-regret gate with honest matched evaluation budgets (Phase 3C).

Online policies share ``EvalBank``: every new (action, scenario) plant rollout
counts once; cache hits are free; offline oracle values are never consulted
during selection.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import permutations

from safe_time_evrp.mpc_central.eval_bank import EvalBank, OfflineOracle
from safe_time_evrp.mpc_central.forks import ForkSpec, all_forks, with_action_order, with_scenario_order


@dataclass
class EvalBudgetResult:
    policy: str
    action: str
    estimated_value: float
    true_value: float
    regret: float
    scenario_evals: int
    wall_seconds: float
    notes: tuple[str, ...]


def _pick_best(estimates: dict[str, float]) -> str:
    return max(estimates, key=lambda a: (estimates[a], a))


def reactive_policy(spec: ForkSpec, oracle: OfflineOracle) -> EvalBudgetResult:
    bank = EvalBank(spec)
    estimates: dict[str, float] = {}
    for action in spec.candidate_actions:
        estimates[action] = bank.evaluate(action, 0).value
    action = _pick_best(estimates)
    best = max(oracle.values.values())
    return EvalBudgetResult(
        policy="reactive",
        action=action,
        estimated_value=estimates[action],
        true_value=oracle.values[action],
        regret=best - oracle.values[action],
        scenario_evals=bank.n_evals,
        wall_seconds=bank.wall_seconds,
        notes=("omega0_only",),
    )


def uniform_rollout(spec: ForkSpec, oracle: OfflineOracle, *, budget: int) -> EvalBudgetResult:
    """Round-robin (action, next unseen scenario) until budget is exhausted."""
    bank = EvalBank(spec)
    actions = list(spec.candidate_actions)
    n_sc = len(spec.scenarios)
    # Pointer per action to next scenario index to try.
    next_k = {a: 0 for a in actions}
    while bank.n_evals < budget:
        progressed = False
        for action in actions:
            if bank.n_evals >= budget:
                break
            k = next_k[action]
            if k >= n_sc:
                continue
            bank.evaluate(action, k)
            next_k[action] = k + 1
            progressed = True
        if not progressed:
            break
    estimates = {}
    for action in actions:
        est = bank.sampled_expectation(action)
        if est is None:
            # No sample — assign -inf so it cannot win.
            estimates[action] = -1e18
        else:
            estimates[action] = est
    action = _pick_best(estimates)
    best = max(oracle.values.values())
    return EvalBudgetResult(
        policy="uniform_rollout",
        action=action,
        estimated_value=estimates[action],
        true_value=oracle.values[action],
        regret=best - oracle.values[action],
        scenario_evals=bank.n_evals,
        wall_seconds=bank.wall_seconds,
        notes=(f"budget={budget}", f"actual_evals={bank.n_evals}"),
    )


def random_allocation(spec: ForkSpec, oracle: OfflineOracle, *, budget: int, seed: int) -> EvalBudgetResult:
    bank = EvalBank(spec)
    rng = random.Random(seed)
    actions = list(spec.candidate_actions)
    pairs = [(a, k) for a in actions for k in range(len(spec.scenarios))]
    rng.shuffle(pairs)
    for action, k in pairs:
        if bank.n_evals >= budget:
            break
        bank.evaluate(action, k)
    estimates = {
        a: (bank.sampled_expectation(a) if bank.sampled_expectation(a) is not None else -1e18) for a in actions
    }
    action = _pick_best(estimates)
    best = max(oracle.values.values())
    return EvalBudgetResult(
        policy="random_allocation",
        action=action,
        estimated_value=estimates[action],
        true_value=oracle.values[action],
        regret=best - oracle.values[action],
        scenario_evals=bank.n_evals,
        wall_seconds=bank.wall_seconds,
        notes=(f"budget={budget}", f"seed={seed}"),
    )


def adaptive_mpc(spec: ForkSpec, oracle: OfflineOracle, *, budget: int) -> EvalBudgetResult:
    """Decision-focused allocation using only bank samples (no oracle)."""
    bank = EvalBank(spec)
    actions = list(spec.candidate_actions)
    # Bootstrap: scenario 0 for each action (or until budget).
    for action in actions:
        if bank.n_evals >= budget:
            break
        bank.evaluate(action, 0)

    def estimate(action: str) -> float:
        est = bank.sampled_expectation(action)
        return -1e18 if est is None else est

    while bank.n_evals < budget:
        ests = {a: estimate(a) for a in actions}
        ranked = sorted(ests, key=lambda a: (ests[a], a), reverse=True)
        leader, challenger = ranked[0], ranked[1] if len(ranked) > 1 else ranked[0]

        # Prefer undersampled among top-2; choose first unsampled scenario index.
        def next_unseen(action: str) -> int | None:
            seen = set(bank.sampled_indices(action))
            for k in range(len(spec.scenarios)):
                if k not in seen:
                    return k
            return None

        target = challenger
        k = next_unseen(challenger)
        if k is None:
            target = leader
            k = next_unseen(leader)
        if k is None:
            # All top-2 fully sampled — fill any remaining unsampled pair.
            filled = False
            for a in actions:
                kk = next_unseen(a)
                if kk is not None:
                    bank.evaluate(a, kk)
                    filled = True
                    break
            if not filled:
                break
            continue
        bank.evaluate(target, k)

    estimates = {a: estimate(a) for a in actions}
    action = _pick_best(estimates)
    best = max(oracle.values.values())
    return EvalBudgetResult(
        policy="adaptive_mpc",
        action=action,
        estimated_value=estimates[action],
        true_value=oracle.values[action],
        regret=best - oracle.values[action],
        scenario_evals=bank.n_evals,
        wall_seconds=bank.wall_seconds,
        notes=(f"budget={budget}", "no_oracle_in_loop"),
    )


def run_fairness_suite(
    *,
    budgets: tuple[int, ...] = (3, 4, 6),
    reverse_actions: bool = True,
    reverse_scenarios: bool = True,
    random_seeds: tuple[int, ...] = (0, 1, 2),
) -> dict:
    """Matched regret comparisons under order permutations and allocation baselines."""
    comparisons: list[dict] = []
    rows: list[dict] = []
    fragile_notes: list[str] = []

    def one_spec(spec: ForkSpec, tag: str) -> None:
        oracle = OfflineOracle.build(spec)
        best_action = oracle.best_action()
        for b in budgets:
            b_eff = max(b, len(spec.candidate_actions))
            uni = uniform_rollout(spec, oracle, budget=b_eff)
            ada = adaptive_mpc(spec, oracle, budget=b_eff)
            rnd_results = [random_allocation(spec, oracle, budget=b_eff, seed=s) for s in random_seeds]
            for res in (uni, ada, *rnd_results):
                assert res.scenario_evals <= b_eff
                rows.append(
                    {
                        "tag": tag,
                        "case_id": spec.case_id,
                        "policy": res.policy,
                        "budget": b_eff,
                        "actual_evals": res.scenario_evals,
                        "wall_seconds": res.wall_seconds,
                        "action": res.action,
                        "true_value": res.true_value,
                        "regret": res.regret,
                        "best_action": best_action,
                        "estimated_value": res.estimated_value,
                        "notes": list(res.notes),
                    }
                )
            if ada.regret + 1e-9 < uni.regret:
                winner = "adaptive_mpc"
            elif uni.regret + 1e-9 < ada.regret:
                winner = "uniform_rollout"
            else:
                winner = "tie"
            comparisons.append(
                {
                    "tag": tag,
                    "case_id": spec.case_id,
                    "budget": b_eff,
                    "uniform_action": uni.action,
                    "adaptive_action": ada.action,
                    "uniform_regret": uni.regret,
                    "adaptive_regret": ada.regret,
                    "uniform_evals": uni.scenario_evals,
                    "adaptive_evals": ada.scenario_evals,
                    "winner": winner,
                    "candidate_order": list(spec.candidate_actions),
                    "scenario_order_lens": [len(s) for s in spec.scenarios],
                }
            )

    for spec in all_forks():
        one_spec(spec, "base")
        if reverse_actions:
            one_spec(with_action_order(spec, tuple(reversed(spec.candidate_actions))), "rev_actions")
        if reverse_scenarios and len(spec.scenarios) > 1:
            # Reverse scenario list and probs together.
            sc = tuple(reversed(spec.scenarios))
            pr = tuple(reversed(spec.scenario_probs))
            one_spec(with_scenario_order(spec, sc, pr), "rev_scenarios")
        # All action permutations for 2-action cases (order falsification).
        if len(spec.candidate_actions) == 2:
            for perm in permutations(spec.candidate_actions):
                if perm == spec.candidate_actions or perm == tuple(reversed(spec.candidate_actions)):
                    continue
                one_spec(with_action_order(spec, perm), f"perm_{'_'.join(perm)}")

    adaptive_better = sum(1 for c in comparisons if c["winner"] == "adaptive_mpc")
    adaptive_worse = sum(1 for c in comparisons if c["winner"] == "uniform_rollout")
    ties = sum(1 for c in comparisons if c["winner"] == "tie")

    # Fragility: base win disappears under rev_actions at same case/budget.
    for c in comparisons:
        if c["tag"] != "base" or c["winner"] != "adaptive_mpc":
            continue
        twin = next(
            (
                x
                for x in comparisons
                if x["tag"] == "rev_actions" and x["case_id"] == c["case_id"] and x["budget"] == c["budget"]
            ),
            None,
        )
        if twin and twin["winner"] != "adaptive_mpc":
            fragile_notes.append(
                f"{c['case_id']} budget={c['budget']}: adaptive win vanishes under reversed candidate order "
                f"(now winner={twin['winner']})"
            )

    if adaptive_better > 0 and adaptive_worse == 0 and not fragile_notes:
        verdict = "GO"
        reason = (
            "Adaptive allocation reduces regret vs honest uniform under matched eval counts "
            "across order stress tests without recorded order fragility."
        )
    elif adaptive_better > 0 and (adaptive_worse > 0 or fragile_notes):
        verdict = "REVISE"
        reason = (
            "Adaptive shows some matched-budget wins, but they are fragile to ordering "
            "and/or sometimes worse than uniform — revise the allocation rule."
        )
    elif adaptive_better == 0 and ties == len(comparisons):
        verdict = "REVISE"
        reason = "No reproducible adaptive advantage over uniform under corrected budgets."
    else:
        verdict = "NO-GO"
        reason = "Adaptive allocation offers no reproducible advantage over fairly budgeted rollout."

    return {
        "verdict": verdict,
        "reason": reason,
        "reference_label": "exhaustive_first_action_ranking_under_causal_reactive_recourse",
        "n_comparisons": len(comparisons),
        "adaptive_better": adaptive_better,
        "adaptive_worse": adaptive_worse,
        "ties": ties,
        "fragile_notes": fragile_notes,
        "comparisons": comparisons,
        "rows": rows,
    }


# Back-compat name used by older tests/docs.
def run_decision_regret_gate(**kwargs) -> dict:
    return run_fairness_suite(**kwargs)
