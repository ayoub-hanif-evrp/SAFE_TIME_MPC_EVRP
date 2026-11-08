"""Finite action generators for generic EVRP–MPC (fleet-level admission)."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState


def global_clock(state: WorldState) -> float:
    """Event clock: max of vehicle clocks (all physical progress observed)."""
    return max(v.time for v in state.vehicles)


def release_due_announcements(net: RoadNetwork, state: WorldState) -> WorldState:
    """Announce customers whose release time ≤ global event clock."""
    clock = global_clock(state)
    announce_at = net.metadata.get("announce_at", {})
    newly = {cid for cid, t in announce_at.items() if float(t) <= clock + 1e-12}
    if not newly - state.announced:
        return state
    return WorldState(
        state.vehicles,
        state.accepted,
        state.completed,
        state.rejected,
        state.announced | newly,
        state.belief,
        state.stage,
        state.model_inconsistent,
    )


def pending_future_releases(net: RoadNetwork, state: WorldState) -> bool:
    announce_at = net.metadata.get("announce_at", {})
    clock = global_clock(state)
    return any(float(t) > clock + 1e-12 and cid not in state.announced for cid, t in announce_at.items())


def episode_complete(net: RoadNetwork, state: WorldState) -> bool:
    """True only when no future releases remain and accepted commitments + depot contract hold."""
    if pending_future_releases(net, state):
        return False
    if not state.accepted.issubset(state.completed):
        return False
    if net.metadata.get("require_depot_return"):
        starts = net.metadata.get("start_nodes", {})
        for v in state.vehicles:
            depot = starts.get(v.vehicle_id, net.depot)
            if v.node != depot:
                return False
    return True


def sync_fleet_clock(net: RoadNetwork, state: WorldState, target: float, theta: float):
    """Wait every idle vehicle up to target time (common event clock)."""
    from safe_time_evrp.dr_dual.transition import apply_action

    s = state
    for v in s.vehicles:
        if v.time + 1e-12 >= target:
            continue
        if v.busy_until > v.time + 1e-12:
            continue
        tr = apply_action(
            net,
            s,
            Action(ActionKind.WAIT, v.vehicle_id, wait_duration=target - v.time),
            theta_star=theta,
        )
        if not tr.ok or tr.state is None:
            return None
        s = tr.state
    return s


def fleet_accept_actions(net: RoadNetwork, state: WorldState) -> list[Action]:
    """ACCEPT is a fleet-level decision after announcement — any free vehicle may issue it."""
    state = release_due_announcements(net, state)
    out: list[Action] = []
    free = [v for v in state.vehicles if v.busy_until <= v.time + 1e-12]
    if not free:
        return []
    # Use first free vehicle as the decision agent ID (acceptance is not location-bound)
    vid = free[0].vehicle_id
    for c in net.customers:
        if (
            c.customer_id in state.announced
            and c.customer_id not in state.accepted
            and c.customer_id not in state.rejected
        ):
            if c.customer_id not in state.completed:
                out.append(Action(ActionKind.ACCEPT, vid, customer_id=c.customer_id))
                out.append(Action(ActionKind.REJECT, vid, customer_id=c.customer_id))
    return out


def legal_actions(net: RoadNetwork, state: WorldState, vehicle_id: str) -> list[Action]:
    """Atomic finite action set at a decision epoch for one free vehicle + fleet admission."""
    state = release_due_announcements(net, state)
    v = state.vehicle(vehicle_id)
    if v.busy_until > v.time + 1e-12:
        return fleet_accept_actions(net, state)
    out: list[Action] = list(fleet_accept_actions(net, state))
    for seg in net.segments_from(v.node):
        out.append(Action(ActionKind.TRAVEL, vehicle_id, segment_id=seg.segment_id))
    for c in net.customers:
        # SERVE only when physically at the customer node and accepted
        if c.node == v.node and c.customer_id in state.accepted and c.customer_id not in state.completed:
            out.append(Action(ActionKind.SERVE, vehicle_id, customer_id=c.customer_id))
    ch = net.charger_at(v.node)
    if ch is not None and v.soc < net.battery - 1e-9:
        out.append(Action(ActionKind.CHARGE_FULL, vehicle_id, charger_id=ch.charger_id))
    # Wait until next announcement if any remain
    announce_at = net.metadata.get("announce_at", {})
    clock = global_clock(state)
    future = [float(t) for cid, t in announce_at.items() if float(t) > clock + 1e-12 and cid not in state.announced]
    if future:
        nxt = min(future)
        if nxt > v.time + 1e-12:
            out.append(Action(ActionKind.WAIT, vehicle_id, wait_duration=nxt - v.time))
    if net.metadata.get("require_depot_return") and state.accepted.issubset(state.completed):
        depot = net.metadata.get("start_nodes", {}).get(vehicle_id, net.depot)
        if v.node != depot:
            for seg in net.segments_from(v.node):
                if seg.destination == depot:
                    out.append(Action(ActionKind.TRAVEL, vehicle_id, segment_id=seg.segment_id))
    seen: set[str] = set()
    uniq: list[Action] = []
    for a in out:
        k = a.key()
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    return uniq


def legal_fleet_actions(net: RoadNetwork, state: WorldState) -> list[Action]:
    """All actions for every free vehicle (fleet decision epoch)."""
    state = release_due_announcements(net, state)
    out: list[Action] = []
    for v in state.vehicles:
        out.extend(legal_actions(net, state, v.vehicle_id))
    # Dedup
    seen: set[str] = set()
    uniq: list[Action] = []
    for a in out:
        k = a.key()
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    return uniq
