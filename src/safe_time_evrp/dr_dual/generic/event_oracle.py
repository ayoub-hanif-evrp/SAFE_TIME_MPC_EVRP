"""Global-event finite-state reference for tiny exhaustive instances.

Belief-state DP: at each observable WorldState (vehicles, sets, belief support),
choose one fleet action maximizing expected continuation. θ never enters the
decision key — only the posterior belief after completed observations.

Returns EXACT_OPTIMUM_FULL_FINITE only when search completes within depth/node
limits on the declared finite action class ``legal_fleet_actions``. Otherwise
FEASIBLE_INCUMBENT / TIME_LIMIT / UNKNOWN — never false PROVEN_INFEASIBLE.
"""

from __future__ import annotations

from safe_time_evrp.dr_dual.generic.actions import (
    episode_complete,
    legal_fleet_actions,
    release_due_announcements,
)
from safe_time_evrp.dr_dual.generic.exact_dp import GenericExactResult, GenericSearchStatus
from safe_time_evrp.dr_dual.generic.history import history_key
from safe_time_evrp.dr_dual.generic.model import initial_generic_state, make_tiny_generic_instance
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action


def solve_event_exact(
    net: RoadNetwork | None = None,
    *,
    noise: float = 0.0,
    depth_limit: int = 10,
    node_limit: int = 20_000,
) -> GenericExactResult:
    """Exhaustive nonanticipative belief-state search over ``legal_fleet_actions``."""
    net = net or make_tiny_generic_instance(n_customers=2, n_vehicles=1)
    state0 = release_due_announcements(net, initial_generic_state(net))
    expanded = 0
    hit_limit = False
    memo: dict[tuple, float | None] = {}

    def belief_value(state: WorldState, depth: int) -> float | None:
        nonlocal expanded, hit_limit
        s = release_due_announcements(net, state)
        if episode_complete(net, s):
            return 0.0
        if depth <= 0:
            # Horizon exhausted: admissible only if commitments already met
            return 0.0 if s.accepted.issubset(s.completed) else None

        key = (history_key(s), depth)
        if key in memo:
            return memo[key]

        acts = legal_fleet_actions(net, s)
        if not acts:
            val = 0.0 if episode_complete(net, s) else None
            memo[key] = val
            return val

        best_local: float | None = None
        for a in acts:
            expanded += 1
            if expanded > node_limit:
                hit_limit = True
                memo[key] = best_local
                return best_local
            exp = 0.0
            ok = True
            for theta, p in zip(s.belief.support, s.belief.probs, strict=True):
                if p <= 0:
                    continue
                tr = apply_action(net, s, a, theta_star=theta, noise=noise)
                if tr.state is None or tr.model_inconsistent or not tr.ok:
                    ok = False
                    break
                cont = belief_value(tr.state, depth - 1)
                if cont is None:
                    ok = False
                    break
                exp += p * (tr.reward_delta + cont)
            if not ok:
                continue
            if best_local is None or exp > best_local:
                best_local = exp
        memo[key] = best_local
        return best_local

    # First-action report (same DP, expose argmax among initial travels + fleet acts)
    firsts = legal_fleet_actions(net, state0)
    scores: dict[str, float] = {}
    best = float("-inf")
    best_key = None
    for first in firsts:
        expanded += 1
        if expanded > node_limit:
            hit_limit = True
            break
        total = 0.0
        ok = True
        for theta, p in zip(state0.belief.support, state0.belief.probs, strict=True):
            if p <= 0:
                continue
            tr = apply_action(net, state0, first, theta_star=theta, noise=noise)
            if tr.state is None or tr.model_inconsistent or not tr.ok:
                ok = False
                break
            cont = belief_value(tr.state, depth_limit - 1)
            if cont is None:
                ok = False
                break
            total += p * (tr.reward_delta + cont)
        if not ok:
            continue
        scores[first.key()] = total
        if total > best:
            best = total
            best_key = first.key()

    scope = f"belief_fleet_legal_actions_depth<={depth_limit}"
    meta = {
        "scores": scores,
        "depth_limit": depth_limit,
        "memo_size": len(memo),
        "nonanticipative": True,
    }
    if hit_limit:
        return GenericExactResult(
            GenericSearchStatus.TIME_LIMIT if best_key is None else GenericSearchStatus.FEASIBLE_INCUMBENT,
            best if best_key else None,
            best_key,
            expanded,
            scope,
            meta,
        )
    if best_key is None:
        return GenericExactResult(
            GenericSearchStatus.UNKNOWN,
            None,
            None,
            expanded,
            scope,
            {**meta, "reason": "no_feasible_first"},
        )
    return GenericExactResult(
        GenericSearchStatus.EXACT_OPTIMUM_FULL_FINITE,
        best,
        best_key,
        expanded,
        scope,
        meta,
    )
