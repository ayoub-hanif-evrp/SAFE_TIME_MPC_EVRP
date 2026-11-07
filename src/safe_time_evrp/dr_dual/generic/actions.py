"""Finite action generators for generic EVRP–MPC (no A/C/S hardcoding)."""

from __future__ import annotations

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import WorldState


def release_due_announcements(net: RoadNetwork, state: WorldState) -> WorldState:
    """Announce customers whose release time ≤ current fleet clock (min vehicle time)."""
    clock = min(v.time for v in state.vehicles)
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


def sync_fleet_clock(net: RoadNetwork, state: WorldState, target: float, theta: float):
    """Wait every idle vehicle up to target time (common event clock)."""
    from safe_time_evrp.dr_dual.transition import apply_action

    s = state
    for v in s.vehicles:
        if v.time + 1e-12 >= target:
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


def legal_actions(net: RoadNetwork, state: WorldState, vehicle_id: str) -> list[Action]:
    """Atomic finite action set for one free vehicle at a decision epoch."""
    state = release_due_announcements(net, state)
    v = state.vehicle(vehicle_id)
    if v.busy_until > v.time + 1e-12:
        return []
    out: list[Action] = []
    for seg in net.segments_from(v.node):
        out.append(Action(ActionKind.TRAVEL, vehicle_id, segment_id=seg.segment_id))
    for c in net.customers:
        if c.node == v.node and c.customer_id in state.announced and c.customer_id not in state.completed:
            if c.customer_id not in state.accepted:
                out.append(Action(ActionKind.ACCEPT, vehicle_id, customer_id=c.customer_id))
            else:
                out.append(Action(ActionKind.SERVE, vehicle_id, customer_id=c.customer_id))
    if net.charger_at(v.node) is not None and v.soc < net.battery - 1e-9:
        out.append(Action(ActionKind.CHARGE_FULL, vehicle_id, charger_id=net.charger_at(v.node).charger_id))
    # Terminal: return to start/depot if required and commitments done
    if net.metadata.get("require_depot_return") and state.accepted.issubset(state.completed):
        depot = net.metadata.get("start_nodes", {}).get(vehicle_id, net.depot)
        if v.node != depot:
            for seg in net.segments_from(v.node):
                if seg.destination == depot:
                    out.append(Action(ActionKind.TRAVEL, vehicle_id, segment_id=seg.segment_id))
    # Deduplicate by key
    seen = set()
    uniq = []
    for a in out:
        k = a.key()
        if k not in seen:
            seen.add(k)
            uniq.append(a)
    return uniq
