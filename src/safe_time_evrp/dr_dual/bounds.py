"""Information-value upper bounds for decision-relevant dual MPC.

DRUB (reference upper bound)
----------------------------
Q_bar(a) = E_theta[ travel(a,theta) + V_OL(x_a(theta), theta) ]
Perfect-information / clairvoyant-after-theta relaxation within the declared
continuation family. Retained as a **reference** upper bound.

Resource envelope bound (REUB)
------------------------------
Inexpensive optimistic relaxation (time / optimistic SOC / optional C). Used for
certified pruning only when it dominates the true Q on tests; otherwise reported
as experimental. See CORRECTION_AUDIT.md.

WITHDRAWN: zero_voi certificate based on equality of known-theta optima.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.exact_oracle import _continuation_value_known_theta, _robust_continuation_ok
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action


@dataclass(frozen=True)
class DecisionRelevantBound:
    action_key: str
    q_bar_clairvoyant: float
    q_bar_resource: float
    zero_voi_status: str
    sound_clairvoyant_ub: bool
    sound_resource_ub_vs_clairvoyant: bool
    notes: tuple[str, ...]

    # Back-compat for tests expecting q_bar
    @property
    def q_bar(self) -> float:
        return self.q_bar_clairvoyant


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


def evaluate_resource_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> float | None:
    """Optimistic envelope without enumerating charge/serve plan trees."""
    del noise
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
        e_ac = net.energy(ac, th)
        if e_ac <= soc_opt + 1e-12:
            t_c = t_after + ac.travel_time
            start_c = max(t_c, cust_c.ready)
            if start_c + cust_c.service_time <= cust_c.due + 1e-12:
                reward += cust_c.reward
                break
    return reward


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
        q_res = float("inf")
    sound_res = q_res + 1e-9 >= q_clair if q_res < float("inf") else False
    notes = [
        "clairvoyant_DRUB_reference_UB",
        "zero_voi_certificate=WITHDRAWN_UNSOUND",
        "do_not_use_min_theta_max_plan_as_L",
    ]
    if q_res < float("inf") and not sound_res:
        notes.append("resource_ub_not_dominating_clairvoyant_do_not_certify_prune")
    return DecisionRelevantBound(
        action_key=action.key(),
        q_bar_clairvoyant=q_clair,
        q_bar_resource=q_res,
        zero_voi_status="WITHDRAWN_UNSOUND",
        sound_clairvoyant_ub=True,
        sound_resource_ub_vs_clairvoyant=sound_res,
        notes=tuple(notes),
    )


def bound_dominates_true_q(q_bar: float, true_q: float, *, tol: float = 1e-9) -> bool:
    return q_bar + tol >= true_q
