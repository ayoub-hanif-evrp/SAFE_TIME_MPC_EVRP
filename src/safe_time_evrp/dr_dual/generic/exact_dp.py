"""Restricted / full finite-policy search with honest status labels."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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


class GenericSearchStatus(str, Enum):
    EXACT_OPTIMUM_RESTRICTED = "EXACT_OPTIMUM_RESTRICTED"
    EXACT_OPTIMUM_FULL_FINITE = "EXACT_OPTIMUM_FULL_FINITE"
    FEASIBLE_INCUMBENT = "FEASIBLE_INCUMBENT"
    UNKNOWN = "UNKNOWN"
    TIME_LIMIT = "TIME_LIMIT"
    PROVEN_INFEASIBLE = "PROVEN_INFEASIBLE"  # only if complete restricted class is empty


@dataclass
class GenericExactResult:
    status: GenericSearchStatus
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
            forced = WorldState(
                post.vehicles,
                post.accepted,
                post.completed,
                post.rejected,
                post.announced,
                DiscreteBelief((theta,), (1.0,)),
                post.stage,
                post.model_inconsistent,
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
    max_len: int = 6,
    node_limit: int = 50_000,
    claim_full_finite: bool = False,
) -> GenericExactResult:
    """Search first-travel + short common-continuation class.

    Default status is EXACT_OPTIMUM_RESTRICTED when the restricted class is fully enumerated.
    claim_full_finite=True is refused unless an independent exhaustive event oracle certifies it.
    """
    net = net or make_tiny_generic_instance()
    state = initial_generic_state(net)
    expanded = 0
    best = float("-inf")
    best_key = None
    scores: dict[str, float] = {}
    incomplete = False

    for first in _first_actions(net, state):
        expanded += 1
        if expanded > node_limit:
            return GenericExactResult(
                GenericSearchStatus.TIME_LIMIT,
                best if best_key else None,
                best_key,
                expanded,
                "restricted_first_travel+common_continuation",
                {"scores": scores, "incomplete": True},
            )
        val = _bayes_after_first(net, state, first, noise=noise, max_len=max_len)
        if val is None:
            continue
        scores[first.key()] = val
        if val > best:
            best = val
            best_key = first.key()

    scope = (
        f"RESTRICTED: first_travel + common_continuation max_len={max_len} "
        f"(not general dynamic EVRP optimum)"
    )
    if best_key is None:
        # Truncated search found nothing — NOT a proof of infeasibility of the full model
        return GenericExactResult(
            GenericSearchStatus.UNKNOWN,
            None,
            None,
            expanded,
            scope,
            {"scores": scores, "reason": "no_feasible_plan_in_restricted_class"},
        )
    if claim_full_finite:
        return GenericExactResult(
            GenericSearchStatus.UNKNOWN,
            best,
            best_key,
            expanded,
            scope,
            {"scores": scores, "note": "full_finite_requires_event_oracle"},
        )
    status = GenericSearchStatus.EXACT_OPTIMUM_RESTRICTED
    if incomplete:
        status = GenericSearchStatus.FEASIBLE_INCUMBENT
    return GenericExactResult(
        status,
        best,
        best_key,
        expanded,
        scope,
        {"scores": scores, "noise": noise, "max_len": max_len},
    )


def to_oracle_result(r: GenericExactResult) -> ExactOracleResult:
    # Map to legacy enum without claiming general EXACT_OPTIMUM
    if r.status is GenericSearchStatus.EXACT_OPTIMUM_RESTRICTED:
        mapped = OracleStatus.EXACT_OPTIMUM
    elif r.status is GenericSearchStatus.TIME_LIMIT:
        mapped = OracleStatus.TIME_LIMIT
    elif r.status is GenericSearchStatus.PROVEN_INFEASIBLE:
        mapped = OracleStatus.PROVEN_INFEASIBLE
    else:
        mapped = OracleStatus.UNKNOWN
    return ExactOracleResult(
        status=mapped,
        value=r.value,
        first_action_key=r.first_action_key,
        policy_note=r.status.value,
        nodes_expanded=r.nodes_expanded,
        scope=r.scope,
        extras={**r.extras, "generic_status": r.status.value},
    )
