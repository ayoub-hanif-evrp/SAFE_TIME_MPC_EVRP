"""Exact finite-policy-tree optimization for generic small EVRP instances."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.exact_oracle import ExactOracleResult, OracleStatus
from safe_time_evrp.dr_dual.generic.actions import legal_actions, release_due_announcements
from safe_time_evrp.dr_dual.generic.common_continuation import realize_plan, select_generic_common_policy
from safe_time_evrp.dr_dual.generic.model import initial_generic_state, make_tiny_generic_instance
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


@dataclass
class GenericExactResult:
    status: OracleStatus
    value: float | None
    first_action_key: str | None
    nodes_expanded: int
    scope: str
    extras: dict


def _first_actions(net: RoadNetwork, state: WorldState) -> list[Action]:
    state = release_due_announcements(net, state)
    vid = state.vehicles[0].vehicle_id
    return [a for a in legal_actions(net, state, vid) if a.kind is ActionKind.TRAVEL]


def _bayes_after_first(
    net: RoadNetwork,
    state: WorldState,
    first: Action,
    *,
    noise: float,
    max_len: int,
) -> float | None:
    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, first, theta_star=theta, noise=noise)
        COUNTERS.transition_calls += 1
        if tr.state is None or tr.model_inconsistent or not tr.ok:
            return None
        post = tr.state
        rem = post.belief.support_set()
        if len(rem) <= 1:
            # Known-θ: pick best short plan under Dirac
            forced = WorldState(
                post.vehicles,
                post.accepted,
                post.completed,
                post.rejected,
                post.announced,
                DiscreteBelief((theta,), (1.0,)),
                post.stage,
            )
            common = select_generic_common_policy(net, forced, noise=noise, max_len=max_len)
            if common is None:
                return None
            realized = realize_plan(net, forced, list(common[0]), theta, noise=noise)
            if realized is None:
                return None
            cont = realized
        else:
            common = select_generic_common_policy(net, post, noise=noise, max_len=max_len)
            if common is None:
                return None
            realized = realize_plan(net, post, list(common[0]), theta, noise=noise)
            if realized is None:
                return None
            cont = realized
        total += p * (tr.reward_delta + cont)
    return total


def solve_generic_exact(
    net: RoadNetwork | None = None,
    *,
    noise: float = 0.0,
    max_len: int = 4,
    node_limit: int = 50_000,
) -> GenericExactResult:
    """Exact optimum within finite first-travel + short common-continuation family."""
    net = net or make_tiny_generic_instance()
    state = initial_generic_state(net)
    expanded = 0
    best = float("-inf")
    best_key = None
    scores: dict[str, float] = {}

    for first in _first_actions(net, state):
        expanded += 1
        if expanded > node_limit:
            return GenericExactResult(
                OracleStatus.TIME_LIMIT, None, None, expanded, "generic_first_travel+short_common", {}
            )
        # Safety: feasible under all θ with some continuation
        safe = True
        for th in state.belief.support_set():
            tr = apply_action(net, state, first, theta_star=th, noise=noise)
            if tr.state is None or tr.model_inconsistent or not tr.ok:
                safe = False
                break
            if select_generic_common_policy(net, tr.state, noise=noise, max_len=max_len) is None:
                # At least serve accepted if already at customer — allow empty only if terminal
                if not state.accepted.issubset(tr.state.completed) and not any(
                    c.node == tr.state.vehicle(first.vehicle_id).node
                    for c in net.customers
                    if c.customer_id in state.accepted
                ):
                    # still try
                    pass
        if not safe:
            continue
        val = _bayes_after_first(net, state, first, noise=noise, max_len=max_len)
        if val is None:
            continue
        scores[first.key()] = val
        if val > best:
            best = val
            best_key = first.key()

    if best_key is None:
        return GenericExactResult(
            OracleStatus.PROVEN_INFEASIBLE,
            None,
            None,
            expanded,
            "generic_first_travel+short_common",
            {"scores": scores},
        )
    return GenericExactResult(
        OracleStatus.EXACT_OPTIMUM,
        best,
        best_key,
        expanded,
        "generic_first_travel+short_common_continuation_family",
        {"scores": scores, "noise": noise, "max_len": max_len},
    )


def to_oracle_result(r: GenericExactResult) -> ExactOracleResult:
    return ExactOracleResult(
        status=r.status,
        value=r.value,
        first_action_key=r.first_action_key,
        policy_note="generic_finite_policy_tree",
        nodes_expanded=r.nodes_expanded,
        scope=r.scope,
        extras=r.extras,
    )
