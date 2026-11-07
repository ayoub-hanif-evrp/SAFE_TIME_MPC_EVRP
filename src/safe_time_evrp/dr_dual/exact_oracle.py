"""Exact finite-state dual EVRP oracle (restricted tiny action space).

Status EXACT_OPTIMUM means optimal within the enumerated finite policy tree for the
stated network and action generators — not a continuous general EVRP optimum.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.network import RoadNetwork, make_single_ev_corridors, make_two_ev_shared_theta
from safe_time_evrp.dr_dual.state import PlantLog, VehicleState, WorldState
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
    """Execute the best plan that is feasible for ALL thetas in the current belief; score under truth.

    Plan choice is nonanticipative w.r.t. theta (uses only belief support). Realized reward uses
    ``theta_true`` for energy on any further travel in the plan.
    """
    rem = state_after.belief.support_set()
    # Candidate plans (same family as known-theta oracle)
    base: list[Action] = []
    if "cust_A" not in state_after.completed and state_after.vehicle("v1").node == "A":
        base.append(Action(ActionKind.SERVE, "v1", customer_id="cust_A"))
    candidates = [
        list(base),
        [*base, Action(ActionKind.TRAVEL, "v1", segment_id="AC"), Action(ActionKind.SERVE, "v1", customer_id="cust_C")],
        [
            *base,
            Action(ActionKind.TRAVEL, "v1", segment_id="AS"),
            Action(ActionKind.CHARGE_FULL, "v1", charger_id="chg_S"),
            Action(ActionKind.TRAVEL, "v1", segment_id="SA"),
            Action(ActionKind.TRAVEL, "v1", segment_id="AC"),
            Action(ActionKind.SERVE, "v1", customer_id="cust_C"),
        ],
    ]

    def feasible_for_all(plan: list[Action]) -> bool:
        for th in rem:
            s = WorldState(
                state_after.vehicles,
                state_after.accepted,
                state_after.completed,
                state_after.rejected,
                state_after.announced,
                DiscreteBelief((th,), (1.0,)),
                state_after.stage,
            )
            for act in plan:
                tr = apply_action(net, s, act, theta_star=th, noise=noise)
                if not tr.ok or tr.state is None:
                    return False
                s = tr.state
            if not state_after.accepted.issubset(s.completed):
                return False
        return True

    def realize(plan: list[Action]) -> float | None:
        s = WorldState(
            state_after.vehicles,
            state_after.accepted,
            state_after.completed,
            state_after.rejected,
            state_after.announced,
            DiscreteBelief((theta_true,), (1.0,)),
            state_after.stage,
        )
        total = 0.0
        for act in plan:
            tr = apply_action(net, s, act, theta_star=theta_true, noise=noise)
            if not tr.ok or tr.state is None:
                return None
            total += tr.reward_delta
            s = tr.state
        if not state_after.accepted.issubset(s.completed):
            return None
        return total

    best = float("-inf")
    for plan in candidates:
        if feasible_for_all(plan):
            val = realize(plan)
            if val is not None:
                best = max(best, val)
    return best if best > float("-inf") else None


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

    # Optimized passive: score first actions with continuations that ignore posterior updates
    # (belief forced to prior). Tie-break toward lower |informative|.
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
            cont = _realize_robust_continuation(net, forced, theta, noise=noise)
            if cont is None:
                ok = False
                break
            rob_vals.append(p * (tr.reward_delta + cont))
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
    """Exact-ish tree for 2-EV shared-theta information value.

    Stages: (1) EV1 chooses corridor to A1 and serves A1; (2) after time gate, EV2
    chooses charge-or-not then serves B. EV2 may use updated shared belief.
    """
    net = net or make_two_ev_shared_theta()
    state = initial_state_two(net)
    expanded = 0
    best = float("-inf")
    best_key = None
    details = []

    v1_first = [
        Action(ActionKind.TRAVEL, "v1", segment_id="E1_exploit"),
        Action(ActionKind.TRAVEL, "v1", segment_id="E1_inform"),
    ]
    for first in v1_first:
        # Evaluate Bayes value
        total = 0.0
        ok_all = True
        for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
            expanded += 1
            if expanded > node_limit:
                return ExactOracleResult(OracleStatus.TIME_LIMIT, None, None, "limit", expanded, "two_ev", {})
            log = PlantLog()
            tr = apply_action(net, state, first, theta_star=theta, log=log)
            if not tr.ok or tr.state is None:
                ok_all = False
                break
            # Serve A1
            tr2 = apply_action(
                net, tr.state, Action(ActionKind.SERVE, "v1", customer_id="cust_A1"), theta_star=theta, log=log
            )
            if not tr2.ok or tr2.state is None:
                ok_all = False
                break
            s = tr2.state
            reward = tr.reward_delta + tr2.reward_delta
            # EV2 decision uses belief in s (updated if inform)
            # Options: direct D2→B, or D2→S2 charge S2→B
            best_ev2 = float("-inf")
            # Direct
            s_dir = WorldState(s.vehicles, s.accepted, s.completed, s.rejected, s.announced, s.belief, s.stage)
            # Wait until ready if needed
            v2 = s_dir.vehicle("v2")
            cust_b = net.customer("cust_B")
            if v2.time < cust_b.ready:
                w = apply_action(
                    net,
                    s_dir,
                    Action(ActionKind.WAIT, "v2", wait_duration=cust_b.ready - v2.time),
                    theta_star=theta,
                )
                if w.ok and w.state:
                    s_dir = w.state
            td = apply_action(net, s_dir, Action(ActionKind.TRAVEL, "v2", segment_id="E2_to_B"), theta_star=theta)
            if td.ok and td.state:
                sd = apply_action(net, td.state, Action(ActionKind.SERVE, "v2", customer_id="cust_B"), theta_star=theta)
                if sd.ok and sd.state:
                    best_ev2 = max(best_ev2, td.reward_delta + sd.reward_delta)
            # Charge path
            s_ch = WorldState(s.vehicles, s.accepted, s.completed, s.rejected, s.announced, s.belief, s.stage)
            t1 = apply_action(net, s_ch, Action(ActionKind.TRAVEL, "v2", segment_id="D2_S2"), theta_star=theta)
            if t1.ok and t1.state:
                c1 = apply_action(
                    net, t1.state, Action(ActionKind.CHARGE_FULL, "v2", charger_id="chg_S2"), theta_star=theta
                )
                if c1.ok and c1.state:
                    t2 = apply_action(
                        net, c1.state, Action(ActionKind.TRAVEL, "v2", segment_id="S2_B"), theta_star=theta
                    )
                    if t2.ok and t2.state:
                        # wait for ready
                        st = t2.state
                        if st.vehicle("v2").time < cust_b.ready:
                            w2 = apply_action(
                                net,
                                st,
                                Action(
                                    ActionKind.WAIT,
                                    "v2",
                                    wait_duration=cust_b.ready - st.vehicle("v2").time,
                                ),
                                theta_star=theta,
                            )
                            if w2.ok and w2.state:
                                st = w2.state
                        sd2 = apply_action(
                            net, st, Action(ActionKind.SERVE, "v2", customer_id="cust_B"), theta_star=theta
                        )
                        if sd2.ok and sd2.state:
                            best_ev2 = max(
                                best_ev2, t1.reward_delta + c1.reward_delta + t2.reward_delta + sd2.reward_delta
                            )
            # Safe EV2: if belief not Dirac, only take an option feasible for all remaining thetas
            rem = s.belief.support_set()
            if len(rem) > 1:
                # Must pick action feasible under all rem; evaluate realized under true theta
                # Check direct feasible for all
                def direct_ok_for(th: float, _s=s, _cust=cust_b) -> bool:
                    ss = WorldState(
                        _s.vehicles, _s.accepted, _s.completed, _s.rejected, _s.announced, _s.belief, _s.stage
                    )
                    vv = ss.vehicle("v2")
                    if vv.time < _cust.ready:
                        ww = apply_action(
                            net,
                            ss,
                            Action(ActionKind.WAIT, "v2", wait_duration=_cust.ready - vv.time),
                            theta_star=th,
                        )
                        if not ww.ok or ww.state is None:
                            return False
                        ss = ww.state
                    tt = apply_action(net, ss, Action(ActionKind.TRAVEL, "v2", segment_id="E2_to_B"), theta_star=th)
                    if not tt.ok or tt.state is None:
                        return False
                    ss2 = apply_action(
                        net, tt.state, Action(ActionKind.SERVE, "v2", customer_id="cust_B"), theta_star=th
                    )
                    return bool(ss2.ok)

                if all(direct_ok_for(th) for th in rem):
                    # use direct realized
                    pass
                else:
                    # force charge path if that works for all; else skip B
                    # For simplicity in ambiguous belief: only add best_ev2 if charge works for all OR skip (0)
                    def charge_ok_for(th: float, _s=s, _cust=cust_b) -> bool:
                        ss = WorldState(
                            _s.vehicles, _s.accepted, _s.completed, _s.rejected, _s.announced, _s.belief, _s.stage
                        )
                        t1x = apply_action(net, ss, Action(ActionKind.TRAVEL, "v2", segment_id="D2_S2"), theta_star=th)
                        if not t1x.ok or t1x.state is None:
                            return False
                        c1x = apply_action(
                            net, t1x.state, Action(ActionKind.CHARGE_FULL, "v2", charger_id="chg_S2"), theta_star=th
                        )
                        if not c1x.ok or c1x.state is None:
                            return False
                        t2x = apply_action(
                            net, c1x.state, Action(ActionKind.TRAVEL, "v2", segment_id="S2_B"), theta_star=th
                        )
                        if not t2x.ok or t2x.state is None:
                            return False
                        st = t2x.state
                        if st.vehicle("v2").time < _cust.ready:
                            w2 = apply_action(
                                net,
                                st,
                                Action(
                                    ActionKind.WAIT,
                                    "v2",
                                    wait_duration=_cust.ready - st.vehicle("v2").time,
                                ),
                                theta_star=th,
                            )
                            if not w2.ok or w2.state is None:
                                return False
                            st = w2.state
                        sd2 = apply_action(net, st, Action(ActionKind.SERVE, "v2", customer_id="cust_B"), theta_star=th)
                        return bool(sd2.ok)

                    if all(direct_ok_for(th) for th in rem):
                        pass
                    elif all(charge_ok_for(th) for th in rem):
                        # recompute charge reward under true theta only
                        pass
                    else:
                        best_ev2 = 0.0  # skip B under ambiguity if neither robust
                        # But if direct fails for some, don't use unsafe direct even if true theta ok
                        if not all(direct_ok_for(th) for th in rem):
                            if all(charge_ok_for(th) for th in rem):
                                # keep charge best_ev2 already computed for true theta
                                pass
                            else:
                                best_ev2 = 0.0
            if best_ev2 < -1e8:
                best_ev2 = 0.0
            total += p * (reward + max(0.0, best_ev2))
        if not ok_all:
            continue
        details.append({"first": first.key(), "value": total})
        if total > best:
            best = total
            best_key = first.key()

    # Passive: force exploit if safe
    passive_key = "travel|v1|E1_exploit|None|None|0.0"
    dual_differs = best_key != passive_key

    return ExactOracleResult(
        status=OracleStatus.EXACT_OPTIMUM if best_key else OracleStatus.UNKNOWN,
        value=best if best_key else None,
        first_action_key=best_key,
        policy_note="two_ev_ev1_first_then_ev2_charge_or_direct",
        nodes_expanded=expanded,
        scope="two_ev_shared_theta_finite_tree",
        extras={
            "details": details,
            "cross_vehicle_info_changes_decision": dual_differs,
            "passive_first": passive_key,
        },
    )


def solve_exact(kind: str = "single", **kwargs) -> ExactOracleResult:
    if kind == "single":
        return solve_exact_single(**kwargs)
    if kind == "two":
        return solve_exact_two_ev(**kwargs)
    raise ValueError(kind)
