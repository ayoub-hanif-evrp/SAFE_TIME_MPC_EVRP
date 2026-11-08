"""Generic resource bounds for dynamic EVRP–MPC.

QUARANTINE (Nov 2026 audit): the previous TEI bound that counted only post-travel
announced/accepted customers is **invalid** on the dynamic-request model (omits
later announcements). See ``counterexamples.old_bound_undercounts_future_announcement``.

Certified pruning for the wider dynamic model must use:
  - ``evaluate_trivial_safe_reward_bound`` (proved optimistic), or
  - a future repaired TEI bound that survives adversarial tests.

``evaluate_generic_resource_bound`` returns UNSUPPORTED_BOUND (never VALID / PROVEN_INFEASIBLE).
"""

from __future__ import annotations

from collections import deque

from safe_time_evrp.dr_dual.actions import Action
from safe_time_evrp.dr_dual.bound_result import BoundResult, BoundStatus
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
    max_charges: int = 2,
    state_limit: int = 2000,
) -> str:
    """Return 'reachable' | 'unreachable' | 'unknown' (search cutoff)."""
    q = deque([(origin, soc, t0, 0)])
    seen: set[tuple] = set()
    while q:
        node, s, t, nchg = q.popleft()
        key = (node, round(s, 1), round(t, 1), nchg)
        if key in seen:
            continue
        seen.add(key)
        if len(seen) >= state_limit:
            return "unknown"
        if node == dest:
            start = max(t, ready)
            if start + service <= due + 1e-12:
                return "reachable"
        for seg in net.segments_from(node):
            e = _min_energy(net, seg, info)
            if e > s + 1e-12:
                continue
            q.append((seg.destination, s - e, t + seg.travel_time, nchg))
        if nchg < max_charges:
            ch = net.charger_at(node)
            if ch is not None and s < net.battery - 1e-9:
                deficit = net.battery - s
                dur = ch.full_charge_time * (deficit / net.battery)
                q.append((node, net.battery, t + dur, nchg + 1))
    return "unreachable"


def evaluate_generic_resource_bound_legacy_unsafe(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> BoundResult:
    """UNSAFE legacy implementation kept only for counterexample reproduction."""
    COUNTERS.resource_bound_evaluations += 1
    if action.segment_id is None:
        return BoundResult.unsupported("no_segment")
    try:
        next(s for s in net.segments if s.segment_id == action.segment_id)
    except StopIteration:
        return BoundResult.unsupported("unknown_segment")
    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        if tr.state is None or tr.model_inconsistent or not tr.ok:
            return BoundResult.unknown("legacy_branch_failed")
        post = tr.state
        vv = post.vehicle(action.vehicle_id)
        info = post.belief.support_set()
        reward = tr.reward_delta
        # BUG: only currently announced — omits future releases
        pending = (post.accepted | (post.announced - post.rejected)) - post.completed
        for cid in pending:
            cust = net.customer(cid)
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
            if ok == "reachable":
                reward += cust.reward
        total += p * reward
    return BoundResult(BoundStatus.VALID_BOUND, total, ("LEGACY_UNSAFE_for_counterexample_only",))


def evaluate_trivial_safe_reward_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
    horizon_time: float | None = None,
) -> BoundResult:
    """Trivial proved UB: all rewards that can become eligible within the horizon; ignore costs.

    Q*(a) ≤ E[r_travel(a)] + sum_{eligible customers} reward_c
    because future energy/time costs are nonnegative and at most one service reward per customer.
    Eligible = announced by horizon_time OR accepted OR release_time ≤ horizon.
    """
    COUNTERS.resource_bound_evaluations += 1
    if action.segment_id is None:
        return BoundResult.unsupported("trivial_bound_needs_travel")
    try:
        next(s for s in net.segments if s.segment_id == action.segment_id)
    except StopIteration:
        return BoundResult.unsupported("unknown_segment")
    # Horizon: max customer due (conservative for eligibility of releases)
    if horizon_time is None:
        horizon_time = max((c.due for c in net.customers), default=100.0)
    announce_at = net.metadata.get("announce_at", {})
    eligible = set(state.accepted)
    for c in net.customers:
        rel = float(announce_at.get(c.customer_id, 0.0))
        if rel <= horizon_time + 1e-12:
            eligible.add(c.customer_id)
    reward_cap = sum(net.customer(cid).reward for cid in eligible if cid not in state.completed)

    total = 0.0
    for theta, p in zip(state.belief.support, state.belief.probs, strict=True):
        if p <= 0:
            continue
        tr = apply_action(net, state, action, theta_star=theta, noise=noise)
        COUNTERS.transition_calls += 1
        if tr.state is None or (not tr.ok and not tr.model_inconsistent):
            return BoundResult.unknown("first_travel_failed")
        if tr.model_inconsistent:
            return BoundResult.unknown("model_inconsistent")
        # Optimistic: travel reward + full remaining eligible reward pool
        # (travel reward already negative energy; still ≤ travel + reward_cap)
        total += p * (tr.reward_delta + reward_cap)
    return BoundResult.valid(total, "trivial_safe_eligible_rewards_ignore_future_costs", f"horizon={horizon_time}")


def evaluate_generic_resource_bound(
    net: RoadNetwork,
    state: WorldState,
    action: Action,
    *,
    noise: float = 0.0,
) -> BoundResult:
    """Quarantined: never returns VALID_BOUND or PROVEN_INFEASIBLE for dynamic model."""
    del noise
    COUNTERS.resource_bound_evaluations += 1
    if net.metadata.get("generic"):
        return BoundResult.unsupported(
            "QUARANTINED_legacy_TEI_invalid_on_dynamic_announcements",
            "use_evaluate_trivial_safe_reward_bound",
        )
    return BoundResult.unsupported("generic_TEI_quarantined_outside_legacy_family")
