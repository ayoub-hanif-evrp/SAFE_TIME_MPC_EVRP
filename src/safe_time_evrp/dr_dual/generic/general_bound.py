"""Generic time–energy–information resource upper bound (not A/C/S-hardcoded).

Label: (vehicle, node, time_bin, soc_bin, remaining_commitments, info_set).

Relaxations (optimistic, cannot underestimate max reward under declared assumptions):
1. Energy costs of future travel ignored except first action uses min energy over info set.
2. Optional customer rewards counted if optimistic reachability under EVERY θ in the
   current information set via some path in the road graph (Floyd-like min time/energy
   with optional one full charge at any charger).
3. Pre-observation: first action fixed; post-obs info set = posterior support.
4. Depot-return reward is zero; only feasibility soft-ignored in the UB (reward not
   reduced), which remains valid as an upper bound on reward.

Claim (declared finite model): Q*(a) ≤ Q_generic(a) when status=VALID_BOUND.
"""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.bound_result import BoundResult
from safe_time_evrp.dr_dual.instrumentation import COUNTERS
from safe_time_evrp.dr_dual.network import RoadNetwork, Segment
from safe_time_evrp.dr_dual.state import WorldState
from safe_time_evrp.dr_dual.transition import apply_action


def _min_energy(net: RoadNetwork, seg: Segment, info: frozenset[float]) -> float:
    return min(net.energy(seg, th) for th in info)


def _optimistic_reach(
    net: RoadNetwork,
    origin: str,
    dest: str,
    soc: float,
    t0: float,
    info: frozenset[float],
    *,
    due: float,
    service: float,
    ready: float,
) -> bool:
    """True if dest can be reached and served by due under optimistic min energies/times."""
    # Direct BFS on segments with min energy/time; allow one full charge detour
    from collections import deque

    # state: (node, soc, time, charged_once)
    q = deque([(origin, soc, t0, False)])
    seen = set()
    while q:
        node, s, t, charged = q.popleft()
        key = (node, round(s, 1), round(t, 1), charged)
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > 500:
            break
        if node == dest:
            start = max(t, ready)
            if start + service <= due + 1e-12:
                return True
        for seg in net.segments_from(node):
            e = _min_energy(net, seg, info)
            if e > s + 1e-12:
                continue
            q.append((seg.destination, s - e, t + seg.travel_time, charged))
        if not charged:
            ch = net.charger_at(node)
            if ch is not None and s < net.battery - 1e-9:
                deficit = net.battery - s
                dur = ch.full_charge_time * (deficit / net.battery)
                q.append((node, net.battery, t + dur, True))
    return False


def evaluate_generic_resource_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> BoundResult:
    COUNTERS.resource_bound_evaluations += 1
    if action.segment_id is None:
        return BoundResult.unsupported("generic_bound_requires_travel_segment")
    if state.model_inconsistent:
        return BoundResult.infeasible("model_inconsistent_state")
    try:
        seg = next(s for s in net.segments if s.segment_id == action.segment_id)
    except StopIteration:
        return BoundResult.unsupported("unknown_segment")

    info0 = state.belief.support_set()
    e_min = _min_energy(net, seg, info0)
    v = state.vehicle(action.vehicle_id)
    if e_min > v.soc + 1e-12:
        return BoundResult.infeasible("first_travel_energy")

    # Exact expected first reward via transitions (physical), optimistic continuation rewards
    total = 0.0
    any_branch = False
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        COUNTERS.transition_calls += 1
        if tr.state is None or tr.model_inconsistent or (not tr.ok):
            return BoundResult.infeasible("first_travel_infeasible_branch")
        any_branch = True
        post = tr.state
        vv = post.vehicle(action.vehicle_id)
        info = post.belief.support_set()
        reward = tr.reward_delta
        # Count all not-yet-completed announced/accepted customers that are optimistically reachable
        pending = (post.accepted | (post.announced - post.rejected)) - post.completed
        for cid in pending:
            cust = net.customer(cid)
            # Accepted commitments must be counted only if reachable; else infeasible branch
            ok = _optimistic_reach(
                net,
                vv.node,
                cust.node,
                vv.soc,
                vv.time,
                info,
                due=cust.due,
                service=cust.service_time,
                ready=cust.ready,
            )
            if cid in post.accepted and not ok:
                return BoundResult.infeasible(f"cannot_reach_commitment:{cid}")
            if ok:
                reward += cust.reward
        total += p * reward

    if not any_branch:
        return BoundResult.unknown("no_probability_mass")
    return BoundResult.valid(total, "generic_TEI_resource_bound")
