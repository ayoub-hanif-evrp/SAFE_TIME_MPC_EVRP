"""Nonanticipative two-EV exact oracle with a shared observation clock.

Policy class (exact within this class only)
------------------------------------------
1. EV1 chooses a first corridor (exploit/inform).
2. EV1 travels and serves A1; observation time T_obs = EV1 clock after travel.
3. History key h = (corridor_id, frozenset(posterior support)).
4. EV2 may use the posterior only at decision times t >= T_obs.
5. For each h, EV2 selects ONE action in {DIRECT, CHARGE, SKIP} maximizing
   E[reward | h]; the same action is used for every theta mapping to h.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.exact_oracle import ExactOracleResult, OracleStatus, initial_state_two
from safe_time_evrp.dr_dual.network import RoadNetwork, make_two_ev_shared_theta
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


class Ev2Action(str, Enum):
    DIRECT = "direct"
    CHARGE = "charge"
    SKIP = "skip"


def _sync_wait(net: RoadNetwork, state: WorldState, vid: str, target_time: float, theta: float) -> WorldState | None:
    v = state.vehicle(vid)
    if v.time + 1e-12 >= target_time:
        return state
    tr = apply_action(
        net,
        state,
        Action(ActionKind.WAIT, vid, wait_duration=target_time - v.time),
        theta_star=theta,
    )
    return tr.state if tr.ok else None


def _realize_ev2(
    net: RoadNetwork,
    state: WorldState,
    act: Ev2Action,
    theta: float,
    *,
    info_available: bool,
) -> float | None:
    """Realize EV2 action. If info_available is False, belief must remain prior (caller ensures)."""
    del info_available
    cust_b = net.customer("cust_B")
    s = state
    if act is Ev2Action.SKIP:
        return 0.0
    if act is Ev2Action.DIRECT:
        if s.vehicle("v2").time < cust_b.ready:
            s2 = _sync_wait(net, s, "v2", cust_b.ready, theta)
            if s2 is None:
                return None
            s = s2
        td = apply_action(net, s, Action(ActionKind.TRAVEL, "v2", segment_id="E2_to_B"), theta_star=theta)
        if not td.ok or td.state is None:
            return None
        sd = apply_action(net, td.state, Action(ActionKind.SERVE, "v2", customer_id="cust_B"), theta_star=theta)
        if not sd.ok or sd.state is None:
            return None
        return td.reward_delta + sd.reward_delta
    # CHARGE
    t1 = apply_action(net, s, Action(ActionKind.TRAVEL, "v2", segment_id="D2_S2"), theta_star=theta)
    if not t1.ok or t1.state is None:
        return None
    c1 = apply_action(net, t1.state, Action(ActionKind.CHARGE_FULL, "v2", charger_id="chg_S2"), theta_star=theta)
    if not c1.ok or c1.state is None:
        return None
    t2 = apply_action(net, c1.state, Action(ActionKind.TRAVEL, "v2", segment_id="S2_B"), theta_star=theta)
    if not t2.ok or t2.state is None:
        return None
    st = t2.state
    if st.vehicle("v2").time < cust_b.ready:
        st2 = _sync_wait(net, st, "v2", cust_b.ready, theta)
        if st2 is None:
            return None
        st = st2
    sd = apply_action(net, st, Action(ActionKind.SERVE, "v2", customer_id="cust_B"), theta_star=theta)
    if not sd.ok or sd.state is None:
        return None
    return t1.reward_delta + c1.reward_delta + t2.reward_delta + sd.reward_delta


def _history_key(corridor: str, belief: DiscreteBelief) -> tuple:
    return (corridor, tuple(sorted(belief.support_set())))


@dataclass
class _Branch:
    theta: float
    prob: float
    state_after_ev1: WorldState
    t_obs: float
    ev1_reward: float
    history: tuple


def solve_exact_two_ev_nonanticipative(
    net: RoadNetwork | None = None,
    *,
    node_limit: int = 100_000,
) -> ExactOracleResult:
    net = net or make_two_ev_shared_theta()
    state0 = initial_state_two(net)
    prior = state0.belief
    expanded = 0
    best_val = float("-inf")
    best_first = None
    details = []

    for first in (
        Action(ActionKind.TRAVEL, "v1", segment_id="E1_exploit"),
        Action(ActionKind.TRAVEL, "v1", segment_id="E1_inform"),
    ):
        branches: list[_Branch] = []
        ok = True
        for theta, p in zip(prior.support, prior.probs, strict=True):
            if p <= 0:
                continue
            expanded += 1
            if expanded > node_limit:
                return ExactOracleResult(OracleStatus.TIME_LIMIT, None, None, "limit", expanded, "two_ev_nonant", {})
            tr = apply_action(net, state0, first, theta_star=theta)
            if not tr.ok or tr.state is None:
                ok = False
                break
            t_obs = tr.state.vehicle("v1").time
            tr2 = apply_action(net, tr.state, Action(ActionKind.SERVE, "v1", customer_id="cust_A1"), theta_star=theta)
            if not tr2.ok or tr2.state is None:
                ok = False
                break
            # Sync EV2 clock to T_obs before information may be used
            s = tr2.state
            s_sync = _sync_wait(net, s, "v2", t_obs, theta)
            if s_sync is None:
                ok = False
                break
            # Belief already updated by travel; after sync, EV2 may use it
            h = _history_key(first.segment_id or "", s_sync.belief)
            branches.append(
                _Branch(
                    theta=theta,
                    prob=p,
                    state_after_ev1=s_sync,
                    t_obs=t_obs,
                    ev1_reward=tr.reward_delta + tr2.reward_delta,
                    history=h,
                )
            )
        if not ok or not branches:
            continue

        # Group branches by history; pick one EV2 action per history
        by_h: dict[tuple, list[_Branch]] = {}
        for b in branches:
            by_h.setdefault(b.history, []).append(b)

        policy: dict[tuple, Ev2Action] = {}
        for h, group in by_h.items():
            # Mass within group
            z = sum(b.prob for b in group)
            best_act = Ev2Action.SKIP
            best_score = float("-inf")
            for act in (Ev2Action.DIRECT, Ev2Action.CHARGE, Ev2Action.SKIP):
                # Action must be realizable under EVERY theta in the group (common decision)
                scores = []
                feasible = True
                for b in group:
                    r = _realize_ev2(net, b.state_after_ev1, act, b.theta, info_available=True)
                    if r is None and act is not Ev2Action.SKIP:
                        feasible = False
                        break
                    scores.append((b.prob / z) * (0.0 if r is None else r))
                if not feasible:
                    continue
                score = sum(scores)
                if score > best_score:
                    best_score = score
                    best_act = act
            policy[h] = best_act

        # Evaluate expected value under the shared policy
        total = 0.0
        for b in branches:
            act = policy[b.history]
            r2 = _realize_ev2(net, b.state_after_ev1, act, b.theta, info_available=True)
            if r2 is None:
                r2 = 0.0
            total += b.prob * (b.ev1_reward + r2)

        details.append(
            {
                "first": first.key(),
                "value": total,
                "policy_by_history": {str(h): a.value for h, a in policy.items()},
            }
        )
        if total > best_val:
            best_val = total
            best_first = first.key()

    # Cross-vehicle info: inform vs exploit first-action difference
    vals = {d["first"]: d["value"] for d in details}
    cross = False
    if "travel|v1|E1_inform|None|None|0.0" in vals and "travel|v1|E1_exploit|None|None|0.0" in vals:
        cross = abs(vals["travel|v1|E1_inform|None|None|0.0"] - vals["travel|v1|E1_exploit|None|None|0.0"]) > 1e-9

    return ExactOracleResult(
        status=OracleStatus.EXACT_OPTIMUM if best_first else OracleStatus.UNKNOWN,
        value=best_val if best_first else None,
        first_action_key=best_first,
        policy_note="two_ev_history_indexed_nonanticipative",
        nodes_expanded=expanded,
        scope="two_ev_history_indexed_DIRECT_CHARGE_SKIP",
        extras={
            "details": details,
            "cross_vehicle_info_changes_ev1_first_value": cross,
            "nonanticipative": True,
        },
    )


def reverse_ranking_regression() -> dict:
    """Abstract EV2 rewards: DIRECT better under θ=0, CHARGE better under θ=1.

    With ambiguous history, common policy must pick ONE action; expected value is
    max(E[DIRECT], E[CHARGE], 0), not E[max].
    """
    direct = {0.0: 10.0, 1.0: 0.0}
    charge = {0.0: 0.0, 1.0: 10.0}
    clairvoyant = 0.5 * 10 + 0.5 * 10  # 10
    common_best = max(0.5 * sum(direct.values()), 0.5 * sum(charge.values()), 0.0)  # 5
    return {
        "clairvoyant_per_theta_max": clairvoyant,
        "nonanticipative_common_best": common_best,
        "must_not_report_clairvoyant_as_exact": True,
    }
