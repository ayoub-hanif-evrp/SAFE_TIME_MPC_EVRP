"""Information-value upper bounds for decision-relevant dual MPC.

Family-restricted REUB_v1 / DRUB kept as reference methods (frozen).
All evaluators return BoundResult — never bare None for \"unsupported\".
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.bound_result import BoundResult, BoundStatus
from safe_time_evrp.dr_dual.exact_oracle import (
    _bayes_value_after_first,
    _continuation_value_known_theta,
    _robust_continuation_ok,
    initial_state_single,
)
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import (
    ChargerSpec,
    CustomerSpec,
    RoadNetwork,
    Segment,
)
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action


@dataclass(frozen=True)
class DecisionRelevantBound:
    action_key: str
    q_bar_clairvoyant: float
    q_bar_resource: float
    resource_version: str
    zero_voi_status: str
    sound_clairvoyant_ub: bool
    sound_resource_ub_claimed: bool
    resource_status: str
    notes: tuple[str, ...]

    @property
    def q_bar(self) -> float:
        return self.q_bar_clairvoyant

    @property
    def sound_resource_ub_vs_clairvoyant(self) -> bool:
        return self.q_bar_resource + 1e-9 >= self.q_bar_clairvoyant


def evaluate_clairvoyant_bound_result(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> BoundResult:
    COUNTERS.bound_evaluations += 1
    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        COUNTERS.transition_calls += 1
        if not tr.ok or tr.state is None or tr.model_inconsistent:
            return BoundResult.infeasible("clairvoyant_first_infeasible_or_inconsistent")
        if not _robust_continuation_ok(net, tr.state):
            return BoundResult.infeasible("clairvoyant_continuation_not_robust")
        COUNTERS.known_theta_continuation_calls += 1
        v_ol = _continuation_value_known_theta(net, tr.state, theta, noise=noise)
        if v_ol < -1e8:
            return BoundResult.infeasible("clairvoyant_ol_infeasible")
        total += p * (tr.reward_delta + v_ol)
    return BoundResult.valid(total, "DRUB")


def evaluate_clairvoyant_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> float | None:
    """Legacy float API: VALID value or None if infeasible (not unsupported)."""
    r = evaluate_clairvoyant_bound_result(net, state, action, noise=noise)
    if r.status is BoundStatus.VALID_BOUND:
        return r.value
    return None


def evaluate_resource_bound_v0_direct_only(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
) -> float | None:
    """INVALID general UB: ignores charging-enabled customers (kept for counterexample)."""
    COUNTERS.resource_bound_evaluations += 1
    if action.segment_id is None:
        return None
    try:
        seg = next(s for s in net.segments if s.segment_id == action.segment_id)
        ac = next(s for s in net.segments if s.segment_id == "AC")
        cust_a = net.customer("cust_A")
        cust_c = net.customer("cust_C")
    except (StopIteration, KeyError):
        return None
    support = state.belief.support_set()
    e_min = min(net.energy(seg, th) for th in support)
    v = state.vehicle(action.vehicle_id)
    if e_min > v.soc + 1e-12:
        return None
    t_after = v.time + seg.travel_time
    soc_opt = v.soc - e_min
    reward = -net.energy_cost * e_min
    if "cust_A" not in state.completed:
        start = max(t_after, cust_a.ready)
        if start + cust_a.service_time > cust_a.due + 1e-12:
            return None
        reward += cust_a.reward
        t_after = start + cust_a.service_time
    for th in support:
        if net.energy(ac, th) <= soc_opt + 1e-12:
            t_c = t_after + ac.travel_time
            if max(t_c, cust_c.ready) + cust_c.service_time <= cust_c.due + 1e-12:
                reward += cust_c.reward
                break
    return reward


def evaluate_resource_bound_result(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> BoundResult:
    """REUB_v1 family bound with explicit status."""
    del noise
    COUNTERS.resource_bound_evaluations += 1
    if action.segment_id is None:
        return BoundResult.unsupported("no_segment")
    if not net.chargers:
        return BoundResult.unsupported("no_chargers_REUB_v1_requires_S")
    try:
        seg = next(s for s in net.segments if s.segment_id == action.segment_id)
        ac = next(s for s in net.segments if s.segment_id == "AC")
        as_ = next(s for s in net.segments if s.segment_id == "AS")
        sa = next(s for s in net.segments if s.segment_id == "SA")
        ch = net.chargers[0]
        cust_a = net.customer("cust_A")
        cust_c = net.customer("cust_C")
    except (StopIteration, IndexError, KeyError):
        return BoundResult.unsupported("not_AC_S_family")

    support = state.belief.support_set()
    e_min = min(net.energy(seg, th) for th in support)
    v = state.vehicle(action.vehicle_id)
    if e_min > v.soc + 1e-12:
        return BoundResult.infeasible("first_corridor_energy")
    t = v.time + seg.travel_time
    soc = v.soc - e_min
    reward = -net.energy_cost * e_min
    if "cust_A" not in state.completed:
        start = max(t, cust_a.ready)
        if start + cust_a.service_time > cust_a.due + 1e-12:
            return BoundResult.infeasible("cannot_serve_A")
        reward += cust_a.reward
        t = start + cust_a.service_time

    def direct_ok(soc_now: float, t_now: float) -> bool:
        for th in support:
            if net.energy(ac, th) <= soc_now + 1e-12:
                t_c = t_now + ac.travel_time
                if max(t_c, cust_c.ready) + cust_c.service_time <= cust_c.due + 1e-12:
                    return True
        return False

    def charge_then_c_ok(soc_now: float, t_now: float) -> bool:
        e_as = min(net.energy(as_, th) for th in support)
        if e_as > soc_now + 1e-12:
            return False
        t1 = t_now + as_.travel_time
        soc1 = soc_now - e_as
        deficit = net.battery - soc1
        t_chg = ch.full_charge_time * (deficit / net.battery)
        t2 = t1 + t_chg
        e_sa = min(net.energy(sa, th) for th in support)
        if e_sa > net.battery + 1e-12:
            return False
        t3 = t2 + sa.travel_time
        soc3 = net.battery - e_sa
        return direct_ok(soc3, t3)

    if direct_ok(soc, t) or charge_then_c_ok(soc, t):
        reward += cust_c.reward
    return BoundResult.valid(reward, "REUB_v1")


def evaluate_resource_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> float | None:
    r = evaluate_resource_bound_result(net, state, action, noise=noise)
    if r.status is BoundStatus.VALID_BOUND:
        return r.value
    return None


def charging_makes_old_resource_bound_invalid() -> dict:
    segs = (
        Segment("DA_exploit", "D", "A", 5.0, 4.0, 0.0),
        Segment("AS", "A", "S", 1.0, 0.5, 0.0),
        Segment("SA", "S", "A", 1.0, 0.5, 0.0),
        Segment("AC", "A", "C", 3.0, 9.0, 0.0),
    )
    net = RoadNetwork(
        name="reub_v0_invalid_charge",
        nodes=("D", "A", "S", "C"),
        depot="D",
        battery=12.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_A", "A", 0.0, 100.0, 1.0, 10.0),
            CustomerSpec("cust_C", "C", 0.0, 40.0, 1.0, 5.0),
        ),
        chargers=(ChargerSpec("chg_S", "S", 6.0),),
        energy_cost=0.0,
        metadata={"accepted_init": ("cust_A",)},
    )
    state = initial_state_single(net)
    action = Action(ActionKind.TRAVEL, "v1", segment_id="DA_exploit")
    v0 = evaluate_resource_bound_v0_direct_only(net, state, action)
    v1 = evaluate_resource_bound(net, state, action)
    true_q = _bayes_value_after_first(net, state, action, mode="safe_dual")
    return {
        "v0_direct_only": v0,
        "v1_with_charge": v1,
        "true_q": true_q,
        "v0_invalid": true_q is not None and v0 is not None and v0 + 1e-9 < true_q,
        "v1_valid_on_instance": true_q is not None and v1 is not None and v1 + 1e-9 >= true_q,
        "notes": (
            "v0 omits C though charge-then-C is feasible → not a general UB",
            "v1 includes optimistic charge path",
        ),
    }


def evaluate_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> DecisionRelevantBound | None:
    q_clair_r = evaluate_clairvoyant_bound_result(net, state, action, noise=noise)
    if q_clair_r.status is not BoundStatus.VALID_BOUND or q_clair_r.value is None:
        return None
    q_res_r = evaluate_resource_bound_result(net, state, action, noise=noise)
    q_res = q_res_r.value if q_res_r.status is BoundStatus.VALID_BOUND and q_res_r.value is not None else float("-inf")
    return DecisionRelevantBound(
        action_key=action.key(),
        q_bar_clairvoyant=q_clair_r.value,
        q_bar_resource=q_res,
        resource_version="REUB_v1",
        zero_voi_status="WITHDRAWN_UNSOUND",
        sound_clairvoyant_ub=True,
        sound_resource_ub_claimed=q_res_r.status is BoundStatus.VALID_BOUND,
        resource_status=q_res_r.status.value,
        notes=(
            "clairvoyant_DRUB_reference_UB",
            "REUB_v1_frozen_family_reference",
            f"resource_status={q_res_r.status.value}",
            "zero_voi_certificate=WITHDRAWN_UNSOUND",
        ),
    )


def bound_dominates_true_q(q_bar: float, true_q: float, *, tol: float = 1e-9) -> bool:
    return q_bar + tol >= true_q
