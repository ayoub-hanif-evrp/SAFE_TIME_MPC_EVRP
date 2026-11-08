"""Independently derived finite-trajectory route check (no ``evaluate_route`` call).

Used as a cross-check against the nominal B1 validator on small adversarial cases.
Does not claim robust safety of unused future suffixes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.environment.energy import EPS
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Anchor, Visit


@dataclass
class PrimitiveCheckResult:
    ok: bool
    reason: str
    served: list[str] = field(default_factory=list)
    distance: float = 0.0
    charge_time: float = 0.0
    end_time: float = 0.0
    end_soc: float = 0.0


def primitive_check_route(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
) -> PrimitiveCheckResult:
    """Walk arcs with explicit distance/time/energy/load equations from instance tables."""
    vehicle = instance.vehicle_type
    depot = instance.depot_id
    planned = list(visits)
    if not planned or planned[-1].purpose != "return" or planned[-1].node_id != depot:
        planned.append(Visit(depot, "return"))

    node = anchor.node
    time = float(anchor.time)
    soc = float(anchor.soc)
    load = float(anchor.load)
    onboard = set(anchor.onboard)
    distance = 0.0
    charge_time = 0.0
    served: list[str] = []

    # Freight preload at depot for upcoming services (Solomon/Schneider convention).
    if node == depot:
        upcoming = []
        for v in planned:
            if v.purpose in {"reload", "return"}:
                break
            if v.purpose == "service":
                upcoming.append(v.node_id)
        for cid in upcoming:
            if cid in onboard:
                continue
            cust = instance.node(cid)
            if cust.kind is not NodeKind.CUSTOMER:
                return PrimitiveCheckResult(False, "service_target_not_customer", end_time=time, end_soc=soc)
            if load + cust.demand > vehicle.load_capacity + EPS:
                return PrimitiveCheckResult(False, "excess_payload", end_time=time, end_soc=soc)
            onboard.add(cid)
            load += cust.demand

    for index, visit in enumerate(planned):
        if visit.node_id != node:
            try:
                arc = instance.arc(node, visit.node_id)
            except KeyError:
                return PrimitiveCheckResult(False, f"missing_arc:{node}->{visit.node_id}", end_time=time, end_soc=soc)
            # Nominal Schneider energy: use arc.energy directly (independent of evaluate_route).
            used = float(arc.energy)
            if soc - used < -EPS:
                return PrimitiveCheckResult(False, "battery_depleted", end_time=time, end_soc=soc)
            soc -= used
            if soc < 0 and soc >= -EPS:
                soc = 0.0
            time += float(arc.travel_time)
            distance += float(arc.distance)
            node = visit.node_id

        if visit.purpose == "service":
            cust = instance.node(visit.node_id)
            if cust.kind is not NodeKind.CUSTOMER:
                return PrimitiveCheckResult(False, "service_target_not_customer", end_time=time, end_soc=soc)
            if visit.node_id not in onboard:
                return PrimitiveCheckResult(False, "goods_not_onboard", end_time=time, end_soc=soc)
            if time > cust.window.due + EPS:
                return PrimitiveCheckResult(False, "missed_window", end_time=time, end_soc=soc)
            if time < cust.window.ready:
                time = cust.window.ready
            time += cust.service_time
            load -= cust.demand
            if load < -EPS:
                return PrimitiveCheckResult(False, "negative_load", end_time=time, end_soc=soc)
            onboard.discard(visit.node_id)
            served.append(visit.node_id)
        elif visit.purpose == "charge":
            station = instance.node(visit.node_id)
            if station.kind is not NodeKind.CHARGER:
                return PrimitiveCheckResult(False, "charge_away_from_station", end_time=time, end_soc=soc)
            if time > station.window.due + EPS:
                return PrimitiveCheckResult(False, "charger_window", end_time=time, end_soc=soc)
            if time < station.window.ready:
                time = station.window.ready
            target = vehicle.battery_capacity if vehicle.recharge_policy == "full" else visit.charge_target
            if target is None:
                return PrimitiveCheckResult(False, "partial_charge_missing_target", end_time=time, end_soc=soc)
            if target > vehicle.battery_capacity + EPS or target < soc - EPS:
                return PrimitiveCheckResult(False, "impossible_charge", end_time=time, end_soc=soc)
            duration = (target - soc) * vehicle.inverse_recharge_rate
            time += duration
            charge_time += duration
            soc = float(target)
        elif visit.purpose == "reload":
            if node != depot:
                return PrimitiveCheckResult(False, "reload_away_from_depot", end_time=time, end_soc=soc)
            load = 0.0
            onboard.clear()
            upcoming = []
            for v in planned[index + 1 :]:
                if v.purpose in {"reload", "return"}:
                    break
                if v.purpose == "service":
                    upcoming.append(v.node_id)
            for cid in upcoming:
                cust = instance.node(cid)
                if load + cust.demand > vehicle.load_capacity + EPS:
                    return PrimitiveCheckResult(False, "excess_payload", end_time=time, end_soc=soc)
                onboard.add(cid)
                load += cust.demand
        elif visit.purpose == "return":
            if node != depot:
                return PrimitiveCheckResult(False, "return_not_at_depot", end_time=time, end_soc=soc)
            if time > instance.node(depot).window.due + EPS:
                return PrimitiveCheckResult(False, "depot_deadline", end_time=time, end_soc=soc)
        else:
            return PrimitiveCheckResult(False, "unknown_purpose", end_time=time, end_soc=soc)

    if len(served) != len(set(served)):
        return PrimitiveCheckResult(False, "duplicate_service", end_time=time, end_soc=soc)
    return PrimitiveCheckResult(
        True,
        "ok",
        served=served,
        distance=distance,
        charge_time=charge_time,
        end_time=time,
        end_soc=soc,
    )
