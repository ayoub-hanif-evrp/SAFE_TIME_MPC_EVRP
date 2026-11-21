"""M2: residual time/energy slack checks for newly accepted customers."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route, tour_customer_ids
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Observation, Visit


@dataclass(frozen=True)
class CustomerSlack:
    customer_id: str
    vehicle_id: str
    time_slack: float
    energy_on_arrival: float
    end_soc: float
    depot_time_slack: float


def _service_slacks_on_route(
    instance: Instance,
    observation: Observation,
    vehicle_id: str,
    visits: list[Visit],
    energy: NominalLinearEnergy,
) -> dict[str, CustomerSlack]:
    """Re-simulate a route (physics-aligned) and record slack at each service."""
    vehicle = next(v for v in observation.vehicles if v.id == vehicle_id)
    model = energy
    vt = instance.vehicle_type
    depot = instance.depot_id
    planned = list(visits)
    if not planned or planned[-1].purpose != "return" or planned[-1].node_id != depot:
        planned.append(Visit(depot, "return"))

    node = vehicle.anchor.node
    time = float(vehicle.anchor.time)
    soc = float(vehicle.anchor.soc)
    load = float(vehicle.anchor.load)
    onboard = set(vehicle.anchor.onboard)
    out: dict[str, CustomerSlack] = {}

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
        if load + extra > vt.load_capacity + EPS:
            return "excess_payload"
        for cid in ids:
            if cid not in onboard:
                onboard.add(cid)
                load += instance.node(cid).demand
        return None

    if node == depot:
        initial = [cid for cid in tour_customer_ids(planned, 0) if cid not in onboard]
        if load_customers(initial):
            return out

    for index, visit in enumerate(planned):
        if visit.node_id != node:
            try:
                arc = instance.arc(node, visit.node_id)
            except KeyError:
                return out
            used = model.travel_energy(instance, arc, soc=soc, load=load)
            soc -= used
            time += arc.travel_time
            node = visit.node_id
        if visit.purpose == "service":
            cust = instance.node(visit.node_id)
            if cust.kind is not NodeKind.CUSTOMER:
                continue
            time_slack = float(cust.window.due - time)
            energy_on_arrival = float(soc)
            if time < cust.window.ready:
                time = cust.window.ready
            time += cust.service_time
            load -= cust.demand
            onboard.discard(visit.node_id)
            out[visit.node_id] = CustomerSlack(
                customer_id=visit.node_id,
                vehicle_id=vehicle_id,
                time_slack=time_slack,
                energy_on_arrival=energy_on_arrival,
                end_soc=0.0,
                depot_time_slack=0.0,
            )
        elif visit.purpose == "charge":
            station = instance.node(visit.node_id)
            if time < station.window.ready:
                time = station.window.ready
            if vt.recharge_policy == "full":
                target = vt.battery_capacity
            else:
                target = float(visit.charge_target) if visit.charge_target is not None else vt.battery_capacity
            duration = model.charge_duration(
                soc, target, vt.inverse_recharge_rate, battery_capacity=vt.battery_capacity
            )
            time += duration
            soc = target
        elif visit.purpose == "reload":
            load = 0.0
            onboard.clear()
            load_customers(tour_customer_ids(planned, index + 1))
        elif visit.purpose == "return":
            depot_slack = float(instance.node(depot).window.due - time)
            for cid, sl in list(out.items()):
                out[cid] = CustomerSlack(
                    customer_id=sl.customer_id,
                    vehicle_id=sl.vehicle_id,
                    time_slack=sl.time_slack,
                    energy_on_arrival=sl.energy_on_arrival,
                    end_soc=float(soc),
                    depot_time_slack=depot_slack,
                )
    return out


def filter_accepts_by_slack(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    newly_accepted: list[str],
    *,
    gamma_time: float,
    gamma_energy: float,
    energy: NominalLinearEnergy | None = None,
) -> tuple[list[str], list[str], list[dict]]:
    """Return (kept_accepts, stripped_accepts, diagnostics)."""
    model = energy or NominalLinearEnergy()
    if not newly_accepted:
        return [], [], []
    for vid, visits in routes.items():
        veh = next(v for v in observation.vehicles if v.id == vid)
        rr = evaluate_route(instance, veh.anchor, list(visits), model)
        if not rr.feasible:
            return [], list(newly_accepted), [
                {"customer_id": c, "reason": f"route_infeasible:{vid}:{rr.reason}"} for c in newly_accepted
            ]

    slacks: dict[str, CustomerSlack] = {}
    for vid, visits in routes.items():
        slacks.update(_service_slacks_on_route(instance, observation, vid, list(visits), model))

    kept: list[str] = []
    stripped: list[str] = []
    diag: list[dict] = []
    for cid in newly_accepted:
        sl = slacks.get(cid)
        if sl is None:
            stripped.append(cid)
            diag.append({"customer_id": cid, "reason": "not_on_validated_route"})
            continue
        # Customer time + arrival energy only. Do NOT require depot_time_slack /
        # end_soc margins here — that over-stripped type-2 service (r201C10).
        energy_ok = sl.energy_on_arrival >= gamma_energy - EPS
        time_ok = sl.time_slack >= gamma_time - EPS
        if energy_ok and time_ok:
            kept.append(cid)
            diag.append(
                {
                    "customer_id": cid,
                    "kept": True,
                    "time_slack": sl.time_slack,
                    "depot_time_slack": sl.depot_time_slack,
                    "energy_on_arrival": sl.energy_on_arrival,
                    "end_soc": sl.end_soc,
                }
            )
        else:
            stripped.append(cid)
            reason = []
            if not time_ok:
                reason.append(f"time_slack={sl.time_slack:.4f}<{gamma_time}")
            if not energy_ok:
                reason.append(f"energy_on_arrival={sl.energy_on_arrival:.4f}<{gamma_energy}")
            diag.append({"customer_id": cid, "kept": False, "reason": ";".join(reason)})
    return kept, stripped, diag
