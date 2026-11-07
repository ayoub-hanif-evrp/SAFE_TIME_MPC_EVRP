"""Nonanticipative common continuation policies.

A history-to-action (here: open-loop plan) must be identical for all hidden thetas
that share the same observation history. When the belief support has size > 1,
the controller selects ONE plan feasible for every theta in the support, then
realizes that same plan under the true theta for scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief

# RoadNetwork imported for typed continuation_candidates


@dataclass(frozen=True)
class CommonPolicyResult:
    plan: tuple[Action, ...]
    expected_reward: float
    worst_case_reward: float
    per_theta_rewards: dict[float, float]


def continuation_candidates(state_after: WorldState, net: RoadNetwork | None = None) -> list[list[Action]]:
    base: list[Action] = []
    if "cust_A" not in state_after.completed and state_after.vehicle("v1").node == "A":
        base.append(Action(ActionKind.SERVE, "v1", customer_id="cust_A"))
    plans: list[list[Action]] = [list(base)]
    seg_ids = {s.segment_id for s in net.segments} if net is not None else None

    def has(*ids: str) -> bool:
        return seg_ids is None or all(i in seg_ids for i in ids)

    if has("AC"):
        plans.append(
            [
                *base,
                Action(ActionKind.TRAVEL, "v1", segment_id="AC"),
                Action(ActionKind.SERVE, "v1", customer_id="cust_C"),
            ]
        )
    if has("AS", "SA", "AC") and (net is None or net.chargers):
        plans.append(
            [
                *base,
                Action(ActionKind.TRAVEL, "v1", segment_id="AS"),
                Action(ActionKind.CHARGE_FULL, "v1", charger_id="chg_S"),
                Action(ActionKind.TRAVEL, "v1", segment_id="SA"),
                Action(ActionKind.TRAVEL, "v1", segment_id="AC"),
                Action(ActionKind.SERVE, "v1", customer_id="cust_C"),
            ]
        )
    return plans


def realize_plan(
    net: RoadNetwork,
    state: WorldState,
    plan: list[Action],
    theta: float,
    *,
    noise: float = 0.0,
) -> float | None:
    """Simulate a fixed plan under theta; require accepted ⊆ completed at end."""
    COUNTERS.transition_calls += len(plan)
    s = WorldState(
        state.vehicles,
        state.accepted,
        state.completed,
        state.rejected,
        state.announced,
        DiscreteBelief((theta,), (1.0,)),
        state.stage,
    )
    total = 0.0
    for act in plan:
        tr = apply_action(net, s, act, theta_star=theta, noise=noise)
        if not tr.ok or tr.state is None:
            return None
        total += tr.reward_delta
        s = tr.state
    if not state.accepted.issubset(s.completed):
        return None
    return total


def plan_feasible_for_all(
    net: RoadNetwork,
    state: WorldState,
    plan: list[Action],
    thetas: frozenset[float],
    *,
    noise: float = 0.0,
) -> bool:
    return all(realize_plan(net, state, plan, th, noise=noise) is not None for th in thetas)


def select_common_policy(
    net: RoadNetwork,
    state: WorldState,
    *,
    noise: float = 0.0,
    objective: str = "expected",
) -> CommonPolicyResult | None:
    """Choose one plan using only the current belief (no true theta).

    objective:
      - expected: maximize E_θ[R(plan,θ)] under belief (restricted to support with mass>0)
      - worst_case: maximize min_θ R(plan,θ)
    """
    COUNTERS.common_policy_evaluations += 1
    rem = state.belief.support_set()
    if not rem:
        return None
    # Belief masses on remaining support
    mass = {th: p for th, p in zip(state.belief.support, state.belief.probs, strict=True) if th in rem and p > 0}
    z = sum(mass.values())
    if z <= 0:
        return None
    probs = {th: mass[th] / z for th in mass}

    best: CommonPolicyResult | None = None
    best_score = float("-inf")
    for plan in continuation_candidates(state, net):
        if not plan_feasible_for_all(net, state, plan, rem, noise=noise):
            continue
        per: dict[float, float] = {}
        ok = True
        for th in rem:
            r = realize_plan(net, state, plan, th, noise=noise)
            if r is None:
                ok = False
                break
            per[th] = r
        if not ok:
            continue
        exp = sum(probs[th] * per[th] for th in probs)
        worst = min(per.values())
        score = exp if objective == "expected" else worst
        if score > best_score:
            best_score = score
            best = CommonPolicyResult(tuple(plan), exp, worst, per)
    return best


def abstract_p1_p2_counterexample() -> dict:
    """Logical counterexample: min_θ max_π R ≠ max_π min_θ R and ≠ max_π E[R].

    P1: (10, 0), P2: (0, 10) under theta in {0,1} with equal probs.
    """
    plans = {
        "P1": {0.0: 10.0, 1.0: 0.0},
        "P2": {0.0: 0.0, 1.0: 10.0},
    }
    min_max = min(max(plans[p][th] for p in plans) for th in (0.0, 1.0))  # 10
    # max_min
    max_min = max(min(plans[p].values()) for p in plans)  # 0
    # best expected under common plan
    best_exp = max(0.5 * sum(plans[p].values()) for p in plans)  # 5
    return {
        "min_theta_max_plan": min_max,
        "max_plan_min_theta": max_min,
        "max_plan_expected": best_exp,
        "false_L_if_min_max_used": min_max,
        "true_no_info_optimal_expected": best_exp,
        "candidate_worth_7_must_not_be_pruned_by_false_L": True,
    }
