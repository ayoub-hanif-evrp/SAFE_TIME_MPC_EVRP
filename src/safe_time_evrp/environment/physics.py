"""Forward route evaluation shared by the heuristic and the exact toy enumerator.

The replay validator does not call this module. It recomputes battery, load, and
timing from the event log and the instance tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Anchor, Visit

EnergyLike = NominalLinearEnergy


@dataclass
class RouteResult:
    feasible: bool
    reason: str
    distance: float = 0.0
    charge_time: float = 0.0
    end_time: float = 0.0
    end_soc: float = 0.0
    end_load: float = 0.0
    end_node: str = ""
    served: list[str] = field(default_factory=list)
    visits: list[Visit] = field(default_factory=list)


def tour_customer_ids(visits: list[Visit], start: int) -> list[str]:
    chosen: list[str] = []
    for visit in visits[start:]:
        if visit.purpose in {"reload", "return"}:
            break
        if visit.purpose == "service":
            chosen.append(visit.node_id)
    return chosen


def _fail(reason: str, anchor: Anchor) -> RouteResult:
    return RouteResult(
        feasible=False,
        reason=reason,
        end_time=anchor.time,
        end_soc=anchor.soc,
        end_load=anchor.load,
        end_node=anchor.node,
    )


def evaluate_route(
    instance: Instance,
    anchor: Anchor,
    visits: list[Visit],
    energy: EnergyLike | None = None,
) -> RouteResult:
    """Simulate one vehicle suffix, including its depot return.

    Service must start inside the customer window. Waiting until the window opens
    is allowed. Service may extend past the due date, which is the Solomon/Schneider
    convention. Freight for a tour is loaded at the depot and delivered at customers.
    """
    model = energy or NominalLinearEnergy()
    vehicle = instance.vehicle_type
    depot = instance.depot_id
    planned = list(visits)
    if not planned or planned[-1].purpose != "return" or planned[-1].node_id != depot:
        planned.append(Visit(depot, "return"))

    node = anchor.node
    time = anchor.time
    soc = anchor.soc
    load = anchor.load
    onboard = set(anchor.onboard)
    distance = 0.0
    charge_time = 0.0
    served: list[str] = []

    def load_customers(ids: list[str]) -> str | None:
        nonlocal load
        extra = 0.0
        for cid in ids:
            if cid in onboard:
                continue
            cust = instance.node(cid)
            if cust.kind is not NodeKind.CUSTOMER:
                return "service_target_not_customer"
            extra += cust.demand
        if load + extra > vehicle.load_capacity + EPS:
            return "excess_payload"
        for cid in ids:
            if cid not in onboard:
                onboard.add(cid)
                load += instance.node(cid).demand
        return None

    if node == depot:
        initial = [cid for cid in tour_customer_ids(planned, 0) if cid not in onboard]
        problem = load_customers(initial)
        if problem:
            return _fail(problem, anchor)

    for index, visit in enumerate(planned):
        if visit.node_id != node:
            try:
                arc = instance.arc(node, visit.node_id)
            except KeyError:
                return _fail(f"missing_arc:{node}->{visit.node_id}", anchor)
            used = model.travel_energy(instance, arc, soc=soc, load=load)
            if soc - used < -EPS:
                return _fail("battery_depleted", anchor)
            soc -= used
            if soc < 0 and soc >= -EPS:
                soc = 0.0
            time += arc.travel_time
            distance += arc.distance
            node = visit.node_id

        if visit.purpose == "service":
            cust = instance.node(visit.node_id)
            if cust.kind is not NodeKind.CUSTOMER:
                return _fail("service_target_not_customer", anchor)
            if visit.node_id not in onboard:
                return _fail("goods_not_onboard", anchor)
            if time > cust.window.due + EPS:
                return _fail("missed_window", anchor)
            if time < cust.window.ready:
                time = cust.window.ready
            time += cust.service_time
            load -= cust.demand
            if load < -EPS:
                return _fail("negative_load", anchor)
            onboard.discard(visit.node_id)
            served.append(visit.node_id)
        elif visit.purpose == "charge":
            station = instance.node(visit.node_id)
            if station.kind is not NodeKind.CHARGER:
                return _fail("charge_away_from_station", anchor)
            if time > station.window.due + EPS:
                return _fail("charger_window", anchor)
            if time < station.window.ready:
                time = station.window.ready
            if vehicle.recharge_policy == "full":
                target = vehicle.battery_capacity
            else:
                if visit.charge_target is None:
                    return _fail("partial_charge_missing_target", anchor)
                target = visit.charge_target
            if target > vehicle.battery_capacity + EPS or target < soc - EPS:
                return _fail("impossible_charge", anchor)
            duration = model.charge_duration(soc, target, vehicle.inverse_recharge_rate)
            time += duration
            charge_time += duration
            soc = target
        elif visit.purpose == "reload":
            if node != depot:
                return _fail("reload_away_from_depot", anchor)
            depot_node = instance.node(depot)
            if time > depot_node.window.due + EPS:
                return _fail("depot_window", anchor)
            if time < depot_node.window.ready:
                time = depot_node.window.ready
            load = 0.0
            onboard.clear()
            problem = load_customers(tour_customer_ids(planned, index + 1))
            if problem:
                return _fail(problem, anchor)
        elif visit.purpose == "return":
            if node != depot:
                return _fail("return_not_at_depot", anchor)
            if time > instance.node(depot).window.due + EPS:
                return _fail("depot_deadline", anchor)
        else:
            return _fail("unknown_purpose", anchor)

    if len(served) != len(set(served)):
        return _fail("duplicate_service", anchor)
    return RouteResult(
        feasible=True,
        reason="ok",
        distance=distance,
        charge_time=charge_time,
        end_time=time,
        end_soc=soc,
        end_load=load,
        end_node=node,
        served=served,
        visits=planned,
    )
