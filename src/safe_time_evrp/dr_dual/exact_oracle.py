"""Exact finite-state dual EVRP oracle (restricted tiny action space).

Status EXACT_OPTIMUM means optimal within the enumerated finite policy tree for the
stated network and action generators — not a continuous general EVRP optimum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.network import RoadNetwork, make_single_ev_corridors
from safe_time_evrp.dr_dual.state import VehicleState, WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


class OracleStatus(str, Enum):
    EXACT_OPTIMUM = "EXACT_OPTIMUM"
    PROVEN_FEASIBLE = "PROVEN_FEASIBLE"
    PROVEN_INFEASIBLE = "PROVEN_INFEASIBLE"
    UNKNOWN = "UNKNOWN"
    TIME_LIMIT = "TIME_LIMIT"


@dataclass(frozen=True)
class ExactOracleResult:
    status: OracleStatus
    value: float | None
    first_action_key: str | None
    policy_note: str
    nodes_expanded: int
    scope: str
    extras: dict


def initial_state_single(net: RoadNetwork) -> WorldState:
    accepted = frozenset(net.metadata.get("accepted_init", ()))
    announced = frozenset(c.customer_id for c in net.customers)
    v = VehicleState("v1", net.depot, 0.0, net.battery)
    return WorldState(
        vehicles=(v,),
        accepted=accepted,
        completed=frozenset(),
        rejected=frozenset(),
        announced=announced,
        belief=DiscreteBelief.uniform(net.theta_support),
    )


def initial_state_two(net: RoadNetwork) -> WorldState:
    starts = net.metadata["start_nodes"]
    accepted = frozenset(net.metadata.get("accepted_init", ()))
    announced = frozenset(c.customer_id for c in net.customers)
    vehicles = tuple(VehicleState(vid, starts[vid], 0.0, net.battery) for vid in net.metadata["vehicles"])
    return WorldState(
        vehicles=vehicles,
        accepted=accepted,
        completed=frozenset(),
        rejected=frozenset(),
        announced=announced,
        belief=DiscreteBelief.uniform(net.theta_support),
    )


def _first_travel_actions_single(net: RoadNetwork, state: WorldState) -> list[Action]:
    v = state.vehicle("v1")
    out = []
    for seg in net.segments_from(v.node):
        out.append(Action(ActionKind.TRAVEL, "v1", segment_id=seg.segment_id))
    return out


def _continuation_value_known_theta(
    net: RoadNetwork,
    state: WorldState,
    theta: float,
    *,
    noise: float = 0.0,
) -> float:
    """Open-loop best reward from state under known theta (tiny enumeration).

    Plans after arriving somewhere: serve A if needed; optionally go charge full;
    optionally go to C and serve. Exact for this network's small plan family.
    """
    # Generate candidate plan skeletons as action sequences from current state.
    best = float("-inf")

    def try_seq(actions: list[Action]) -> float | None:
        s = state
        # Simulate under Dirac belief on theta for physical feasibility
        s = WorldState(
            vehicles=s.vehicles,
            accepted=s.accepted,
            completed=s.completed,
            rejected=s.rejected,
            announced=s.announced,
            belief=DiscreteBelief((theta,), (1.0,)),
            stage=s.stage,
        )
        total = 0.0
        for act in actions:
            tr = apply_action(net, s, act, theta_star=theta, noise=noise)
            if not tr.ok or tr.state is None:
                return None
            total += tr.reward_delta
            s = tr.state
        # Must complete accepted commitments
        if not state.accepted.issubset(s.completed):
            return None
        return total

    # Family: serve A if at A and not done; then either AC+serve C, or AS+charge+SA+AC+serve C, or stop
    plans: list[list[Action]] = []
    # Always try serving A first if possible
    base: list[Action] = []
    if "cust_A" not in state.completed and state.vehicle("v1").node == "A":
        base.append(Action(ActionKind.SERVE, "v1", customer_id="cust_A"))
    elif "cust_A" not in state.completed:
        # need to be at A — no travel in continuation family from wrong node beyond AS/SA/AC
        pass

    # stop after A
    plans.append(list(base))
    # direct to C
    plans.append(
        [*base, Action(ActionKind.TRAVEL, "v1", segment_id="AC"), Action(ActionKind.SERVE, "v1", customer_id="cust_C")]
    )
    # charge then C
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

    for plan in plans:
        val = try_seq(plan)
        if val is not None:
            best = max(best, val)
    return best if best > float("-inf") else float("-inf")


def _robust_continuation_ok(net: RoadNetwork, state_after_travel: WorldState) -> bool:
    """True if there exists a plan that completes accepted under EVERY theta in belief support."""
    for theta in state_after_travel.belief.support_set():
        if _continuation_value_known_theta(net, state_after_travel, theta) < -1e8:
            # Need at least serve A
            # Check A can be served
            s = state_after_travel
            if "cust_A" in s.accepted and "cust_A" not in s.completed:
                if s.vehicle("v1").node != "A":
                    return False
                tr = apply_action(
                    net,
                    WorldState(
                        s.vehicles,
                        s.accepted,
                        s.completed,
                        s.rejected,
                        s.announced,
                        DiscreteBelief((theta,), (1.0,)),
                        s.stage,
                    ),
                    Action(ActionKind.SERVE, "v1", customer_id="cust_A"),
                    theta_star=theta,
                )
                if not tr.ok:
                    return False
            else:
                return False
    # Stronger: require finite continuation value under each theta for A only
    for theta in state_after_travel.belief.support_set():
        # Minimal: serve A
        s = WorldState(
            state_after_travel.vehicles,
            state_after_travel.accepted,
            state_after_travel.completed,
            state_after_travel.rejected,
            state_after_travel.announced,
            DiscreteBelief((theta,), (1.0,)),
            state_after_travel.stage,
        )
        if "cust_A" not in s.completed:
            tr = apply_action(net, s, Action(ActionKind.SERVE, "v1", customer_id="cust_A"), theta_star=theta)
            if not tr.ok:
                return False
    return True


def _realize_robust_continuation(
    net: RoadNetwork,
    state_after: WorldState,
    theta_true: float,
    *,
    noise: float = 0.0,
) -> float | None:
    """Score the **same** common nonanticipative plan under ``theta_true``.

    Plan selection uses only the current belief (``select_common_policy``). The true
    theta is used solely to realize rewards of that fixed plan — never to choose it.
    """
    from safe_time_evrp.dr_dual.common_policy import realize_plan, select_common_policy

    common = select_common_policy(net, state_after, noise=noise, objective="expected")
    if common is None:
        return None
    return realize_plan(net, state_after, list(common.plan), theta_true, noise=noise)


def common_policy_expected_value(
    net: RoadNetwork,
    state_after: WorldState,
    *,
    noise: float = 0.0,
) -> float | None:
    """Verified feasible-policy value: E[R(π*,θ)] for nonanticipative π* under current belief."""
    from safe_time_evrp.dr_dual.common_policy import select_common_policy

    common = select_common_policy(net, state_after, noise=noise, objective="expected")
    return None if common is None else common.expected_reward


def _bayes_value_after_first(
    net: RoadNetwork,
    state: WorldState,
    first: Action,
    *,
    mode: str,
    noise: float = 0.0,
) -> float | None:
    """Expected reward of first action + causal continuation given posterior.

    After the observation encoded in ``apply_action``'s belief update:
    - if posterior support is a singleton, continuation may be theta-contingent (known-theta OL);
    - otherwise continuation must be a single robust plan feasible for all remaining thetas.
    """
    del mode  # reserved for future scoring variants
    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, first, theta_star=theta, noise=noise)
        if not tr.ok or tr.state is None:
            return None
        post = tr.state.belief.support_set()
        if len(post) <= 1:
            cont = _continuation_value_known_theta(net, tr.state, theta, noise=noise)
        else:
            cont_r = _realize_robust_continuation(net, tr.state, theta, noise=noise)
            cont = cont_r if cont_r is not None else float("-inf")
        if cont < -1e8:
            return None
        total += p * (tr.reward_delta + cont)
    return total


def solve_exact_single(
    net: RoadNetwork | None = None,
    *,
    noise: float = 0.0,
    node_limit: int = 50_000,
) -> ExactOracleResult:
    net = net or make_single_ev_corridors()
    state = initial_state_single(net)
    expanded = 0
    best_val = float("-inf")
    best_key = None
    safe_scores: dict[str, float] = {}

    for first in _first_travel_actions_single(net, state):
        expanded += 1
        if expanded > node_limit:
            return ExactOracleResult(OracleStatus.TIME_LIMIT, None, None, "node_limit", expanded, "single_ev_tree", {})
        # Commitment safety: A must be servable under all theta after this travel
        safe = True
        for theta in state.belief.support_set():
            tr = apply_action(net, state, first, theta_star=theta, noise=noise)
            if not tr.ok or tr.state is None or not _robust_continuation_ok(net, tr.state):
                safe = False
                break
        if not safe:
            continue
        val = _bayes_value_after_first(net, state, first, mode="safe_dual", noise=noise)
        if val is None:
            continue
        safe_scores[first.key()] = val
        if val > best_val:
            best_val = val
            best_key = first.key()

    if best_key is None:
        return ExactOracleResult(
            OracleStatus.PROVEN_INFEASIBLE,
            None,
            None,
            "no_safe_first_action",
            expanded,
            "single_ev_enumerated_first_travel+continuation_family",
            {},
        )

    # Optimized passive: after each first action, force belief back to prior and take the
    # nonanticipative common policy value (no use of the observation). Tie-break: low info.
    from safe_time_evrp.dr_dual.common_policy import realize_plan, select_common_policy

    passive_best = float("-inf")
    passive_key = None
    for first in _first_travel_actions_single(net, state):
        if first.key() not in safe_scores:
            continue
        rob_vals = []
        ok = True
        for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
            tr = apply_action(net, state, first, theta_star=theta, noise=noise)
            if not tr.ok or tr.state is None:
                ok = False
                break
            forced = WorldState(
                tr.state.vehicles,
                tr.state.accepted,
                tr.state.completed,
                tr.state.rejected,
                tr.state.announced,
                state.belief,
                tr.state.stage,
            )
            common = select_common_policy(net, forced, noise=noise, objective="expected")
            if common is None:
                ok = False
                break
            realized = realize_plan(net, forced, list(common.plan), theta, noise=noise)
            if realized is None:
                ok = False
                break
            rob_vals.append(p * (tr.reward_delta + realized))
        if not ok:
            continue
        score = sum(rob_vals)
        seg = next(s for s in net.segments if s.segment_id == first.segment_id)
        tie = -abs(seg.informative) * 1e-6
        if score + tie > passive_best:
            passive_best = score + tie
            passive_key = first.key()

    # Clairvoyant value
    clair = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        best_th = float("-inf")
        for first in _first_travel_actions_single(net, state):
            tr = apply_action(net, state, first, theta_star=theta, noise=noise)
            if not tr.ok or tr.state is None:
                continue
            cont = _continuation_value_known_theta(net, tr.state, theta, noise=noise)
            if cont < -1e8:
                continue
            best_th = max(best_th, tr.reward_delta + cont)
        clair += p * best_th

    return ExactOracleResult(
        status=OracleStatus.EXACT_OPTIMUM,
        value=best_val,
        first_action_key=best_key,
        policy_note="safe_bayes_adaptive_first_travel",
        nodes_expanded=expanded,
        scope="single_ev_enumerated_first_travel+continuation_family",
        extras={
            "safe_action_values": safe_scores,
            "passive_optimized_first": passive_key,
            "passive_optimized_robust_score": passive_best,
            "clairvoyant_value": clair,
            "dual_differs_from_passive": best_key != passive_key,
            "noise": noise,
        },
    )


def solve_exact_two_ev(net: RoadNetwork | None = None, *, node_limit: int = 100_000) -> ExactOracleResult:
    """Exact optimum within the history-indexed nonanticipative two-EV policy class."""
    from safe_time_evrp.dr_dual.fleet_oracle import solve_exact_two_ev_nonanticipative

    return solve_exact_two_ev_nonanticipative(net, node_limit=node_limit)


def passive_value_after_first(
    net: RoadNetwork,
    state: WorldState,
    first: Action,
    *,
    noise: float = 0.0,
) -> float | None:
    """Optimized passive score: travel realizes θ, continuation uses forced prior belief."""
    from safe_time_evrp.dr_dual.common_policy import realize_plan, select_common_policy

    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, first, theta_star=theta, noise=noise)
        if not tr.ok or tr.state is None:
            return None
        forced = WorldState(
            tr.state.vehicles,
            tr.state.accepted,
            tr.state.completed,
            tr.state.rejected,
            tr.state.announced,
            state.belief,
            tr.state.stage,
        )
        common = select_common_policy(net, forced, noise=noise, objective="expected")
        if common is None:
            return None
        realized = realize_plan(net, forced, list(common.plan), theta, noise=noise)
        if realized is None:
            return None
        total += p * (tr.reward_delta + realized)
    return total


def robust_value_after_first(
    net: RoadNetwork,
    state: WorldState,
    first: Action,
    *,
    noise: float = 0.0,
) -> float | None:
    """Robust fixed-uncertainty value: forced prior, maximize worst-case common plan."""
    from safe_time_evrp.dr_dual.common_policy import realize_plan, select_common_policy

    worst = float("inf")
    first_rewards = []
    for theta in state.belief.support_set():
        tr = apply_action(net, state, first, theta_star=theta, noise=noise)
        if not tr.ok or tr.state is None:
            return None
        first_rewards.append(tr.reward_delta)
        forced = WorldState(
            tr.state.vehicles,
            tr.state.accepted,
            tr.state.completed,
            tr.state.rejected,
            tr.state.announced,
            state.belief,
            tr.state.stage,
        )
        common = select_common_policy(net, forced, noise=noise, objective="worst_case")
        if common is None:
            return None
        realized = realize_plan(net, forced, list(common.plan), theta, noise=noise)
        if realized is None:
            return None
        worst = min(worst, tr.reward_delta + realized)
    return None if worst == float("inf") else worst


def solve_exact(kind: str = "single", **kwargs) -> ExactOracleResult:
    if kind == "single":
        return solve_exact_single(**kwargs)
    if kind == "two":
        return solve_exact_two_ev(**kwargs)
    raise ValueError(kind)
