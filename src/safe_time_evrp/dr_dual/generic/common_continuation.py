"""Generic common continuation plans (nonanticipative) for small horizons."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.generic.actions import legal_fleet_actions, release_due_announcements
from safe_time_evrp.dr_dual.generic.policy_class import (
    RESTRICTED_CONTINUATION_MAX_BRANCH,
    RESTRICTED_CONTINUATION_MAX_LEN,
    RESTRICTED_PLAN_CAP,
)
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


def _terminal_ok(net: RoadNetwork, state: WorldState) -> bool:
    """Terminal for a continuation plan: commitments done + depot; future releases optional."""
    if not state.accepted.issubset(state.completed):
        return False
    if net.metadata.get("require_depot_return"):
        starts = net.metadata.get("start_nodes", {})
        for v in state.vehicles:
            depot = starts.get(v.vehicle_id, net.depot)
            if v.node != depot:
                return False
    return True


def realize_plan(
    net: RoadNetwork,
    state: WorldState,
    plan: list[Action],
    theta: float,
    *,
    noise: float = 0.0,
) -> float | None:
    s = WorldState(
        state.vehicles,
        state.accepted,
        state.completed,
        state.rejected,
        state.announced,
        DiscreteBelief((theta,), (1.0,)),
        state.stage,
        state.model_inconsistent,
    )
    total = 0.0
    for act in plan:
        s = release_due_announcements(net, s)
        tr = apply_action(net, s, act, theta_star=theta, noise=noise)
        COUNTERS.transition_calls += 1
        if tr.state is None or (not tr.ok and not tr.model_inconsistent):
            return None
        if tr.model_inconsistent:
            return None
        total += tr.reward_delta
        s = tr.state
    if not _terminal_ok(net, s):
        return None
    return total


def _candidate_plans(net: RoadNetwork, state: WorldState, *, max_len: int, max_branch: int) -> list[list[Action]]:
    """BFS short plans using fleet legal actions (accept/dispatch any free EV)."""
    state = release_due_announcements(net, state)
    plans: list[list[Action]] = [[]]
    frontier = [[]]
    for _ in range(max_len):
        nxt = []
        for pref in frontier:
            probe = next(iter(state.belief.support_set()))
            s = state
            ok = True
            for act in pref:
                s = release_due_announcements(net, s)
                tr = apply_action(net, s, act, theta_star=probe, noise=0.0)
                if not tr.ok or tr.state is None:
                    ok = False
                    break
                s = tr.state
            if not ok:
                continue
            s = release_due_announcements(net, s)
            acts = legal_fleet_actions(net, s)[:max_branch]
            if not acts:
                plans.append(pref)
                continue
            for a in acts:
                nxt.append([*pref, a])
        frontier = nxt
        plans.extend(nxt)
        if len(plans) > RESTRICTED_PLAN_CAP:
            break
    if [[]] not in plans:
        plans.insert(0, [])
    uniq = []
    seen = set()
    for p in plans:
        key = tuple(a.key() for a in p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def select_generic_common_policy(
    net: RoadNetwork,
    state: WorldState,
    *,
    noise: float = 0.0,
    max_len: int = RESTRICTED_CONTINUATION_MAX_LEN,
    max_branch: int = RESTRICTED_CONTINUATION_MAX_BRANCH,
) -> tuple[tuple[Action, ...], float] | None:
    COUNTERS.common_policy_evaluations += 1
    rem = state.belief.support_set()
    mass = {th: p for th, p in zip(state.belief.support, state.belief.probs, strict=True) if th in rem and p > 0}
    z = sum(mass.values())
    if z <= 0:
        return None
    probs = {th: mass[th] / z for th in mass}
    best = None
    best_score = float("-inf")
    for plan in _candidate_plans(net, state, max_len=max_len, max_branch=max_branch):
        per = {}
        ok = True
        for th in rem:
            r = realize_plan(net, state, plan, th, noise=noise)
            if r is None:
                ok = False
                break
            per[th] = r
        if not ok:
            continue
        score = sum(probs[th] * per[th] for th in probs)
        if score > best_score:
            best_score = score
            best = (tuple(plan), score)
    return best
