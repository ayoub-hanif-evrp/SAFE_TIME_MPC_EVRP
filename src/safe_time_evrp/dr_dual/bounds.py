"""Information-value upper bounds for decision-relevant dual MPC.

DRUB — clairvoyant-after-theta reference UB (standard perfect-information relaxation).

REUB_v0 (direct-only) — INVALID in general when charging enables optional customers.
See ``charging_makes_old_resource_bound_invalid``.

REUB_v1 — optimistic resource envelope including an optimistic full-charge detour.
Claim: for the single-EV corridor family with customers {A,C} and one charger S,
Q*(a) <= REUB_v1(a) because any feasible continuation reward is at most
r_A + r_C - c*e_min_travel, and r_C is counted only if an optimistic (min-energy,
min-time) direct or charge-then-C path meets C's window under some theta.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
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
    notes: tuple[str, ...]

    @property
    def q_bar(self) -> float:
        return self.q_bar_clairvoyant

    @property
    def sound_resource_ub_vs_clairvoyant(self) -> bool:
        return self.q_bar_resource + 1e-9 >= self.q_bar_clairvoyant


def evaluate_clairvoyant_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> float | None:
    COUNTERS.bound_evaluations += 1
    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        COUNTERS.transition_calls += 1
        if not tr.ok or tr.state is None:
            return None
        if not _robust_continuation_ok(net, tr.state):
            return None
        COUNTERS.known_theta_continuation_calls += 1
        v_ol = _continuation_value_known_theta(net, tr.state, theta, noise=noise)
        if v_ol < -1e8:
            return None
        total += p * (tr.reward_delta + v_ol)
    return total


def evaluate_resource_bound_v0_direct_only(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
) -> float | None:
    """INVALID general UB: ignores charging-enabled customers (kept for counterexample)."""
    COUNTERS.resource_bound_evaluations += 1
    if action.segment_id is None:
        return None
    seg = next(s for s in net.segments if s.segment_id == action.segment_id)
    support = state.belief.support_set()
    e_min = min(net.energy(seg, th) for th in support)
    v = state.vehicle(action.vehicle_id)
    if e_min > v.soc + 1e-12:
        return None
    t_after = v.time + seg.travel_time
    soc_opt = v.soc - e_min
    reward = -net.energy_cost * e_min
    cust_a = net.customer("cust_A")
    if "cust_A" not in state.completed:
        start = max(t_after, cust_a.ready)
        if start + cust_a.service_time > cust_a.due + 1e-12:
            return None
        reward += cust_a.reward
        t_after = start + cust_a.service_time
    cust_c = net.customer("cust_C")
    ac = next(s for s in net.segments if s.segment_id == "AC")
    for th in support:
        if net.energy(ac, th) <= soc_opt + 1e-12:
            t_c = t_after + ac.travel_time
            if max(t_c, cust_c.ready) + cust_c.service_time <= cust_c.due + 1e-12:
                reward += cust_c.reward
                break
    return reward


def evaluate_resource_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> float | None:
    """REUB_v1: optimistic direct OR optimistic charge-then-C (single-EV {A,C,S} family)."""
    del noise
    COUNTERS.resource_bound_evaluations += 1
    if action.segment_id is None:
        return None
    try:
        seg = next(s for s in net.segments if s.segment_id == action.segment_id)
        ac = next(s for s in net.segments if s.segment_id == "AC")
        as_ = next(s for s in net.segments if s.segment_id == "AS")
        sa = next(s for s in net.segments if s.segment_id == "SA")
        ch = net.chargers[0]
    except (StopIteration, IndexError):
        return None
    support = state.belief.support_set()
    e_min = min(net.energy(seg, th) for th in support)
    v = state.vehicle(action.vehicle_id)
    if e_min > v.soc + 1e-12:
        return None
    t = v.time + seg.travel_time
    soc = v.soc - e_min
    reward = -net.energy_cost * e_min
    cust_a = net.customer("cust_A")
    if "cust_A" not in state.completed:
        start = max(t, cust_a.ready)
        if start + cust_a.service_time > cust_a.due + 1e-12:
            return None
        reward += cust_a.reward
        t = start + cust_a.service_time
    cust_c = net.customer("cust_C")

    def direct_ok(soc_now: float, t_now: float) -> bool:
        for th in support:
            if net.energy(ac, th) <= soc_now + 1e-12:
                t_c = t_now + ac.travel_time
                if max(t_c, cust_c.ready) + cust_c.service_time <= cust_c.due + 1e-12:
                    return True
        return False

    def charge_then_c_ok(soc_now: float, t_now: float) -> bool:
        # Optimistic: min AS energy, charge to full, min SA, then AC under some theta
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
    return reward


def charging_makes_old_resource_bound_invalid() -> dict:
    """Counterexample: direct A→C infeasible; charge-then-C serves C. v0 < true Q*."""
    # Battery 12; corridor energy 4 → SOC 8; AC needs 9 under all theta; charge enables C.
    segs = (
        Segment("DA_exploit", "D", "A", 5.0, 4.0, 0.0),
        Segment("AS", "A", "S", 1.0, 0.5, 0.0),
        Segment("SA", "S", "A", 1.0, 0.5, 0.0),
        Segment("AC", "A", "C", 3.0, 9.0, 0.0),  # needs 9 SOC; post-exploit has 8
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
    q_clair = evaluate_clairvoyant_bound(net, state, action, noise=noise)
    if q_clair is None:
        return None
    q_res = evaluate_resource_bound(net, state, action, noise=noise)
    if q_res is None:
        q_res = float("-inf")
    notes = [
        "clairvoyant_DRUB_reference_UB",
        "REUB_v1_optimistic_charge_envelope_single_ev_AC_family",
        "REUB_v0_invalidated_by_charging_counterexample",
        "zero_voi_certificate=WITHDRAWN_UNSOUND",
        "certified_prune_uses_clairvoyant_DRUB_only_unless_v1_independently_trusted",
    ]
    return DecisionRelevantBound(
        action_key=action.key(),
        q_bar_clairvoyant=q_clair,
        q_bar_resource=q_res,
        resource_version="REUB_v1",
        zero_voi_status="WITHDRAWN_UNSOUND",
        sound_clairvoyant_ub=True,
        sound_resource_ub_claimed=True,  # claimed for declared single-EV {A,C,S} family only
        notes=tuple(notes),
    )


def bound_dominates_true_q(q_bar: float, true_q: float, *, tol: float = 1e-9) -> bool:
    return q_bar + tol >= true_q
