"""Independent plan validator for Gate 3C (stricter than NN energy-only replay)."""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Anchor, Visit


@dataclass
class ValidationReport:
    feasible: bool
    reasons: list[str] = field(default_factory=list)
    served: list[str] = field(default_factory=list)
    total_distance: float = 0.0
    total_charge_time: float = 0.0
    vehicles_used: int = 0


def validate_fleet_plan(
    instance: Instance,
    routes: dict[str, list[Visit]],
    *,
    start_time: float = 0.0,
    require_all_customers: bool = True,
    energy: NominalLinearEnergy | None = None,
) -> ValidationReport:
    """Validate payload, energy, adaptive/full charge, windows, and depot return."""
    model = energy or NominalLinearEnergy()
    soc0 = instance.vehicle_type.battery_capacity
    served: list[str] = []
    reasons: list[str] = []
    distance = 0.0
    charge_time = 0.0
    used = 0
    for vid, visits in sorted(routes.items()):
        if not visits:
            continue
        used += 1
        anchor = Anchor(instance.depot_id, start_time, soc0, 0.0, frozenset())
        result = evaluate_route(instance, anchor, visits, model)
        if not result.feasible:
            reasons.append(f"{vid}:{result.reason}")
            continue
        # Extra depot deadline already inside evaluate_route.
        # Reject charge visits without targets under partial policy.
        if instance.vehicle_type.recharge_policy == "partial":
            for visit in result.visits:
                if visit.purpose == "charge" and visit.charge_target is None:
                    reasons.append(f"{vid}:partial_charge_missing_target")
        distance += result.distance
        charge_time += result.charge_time
        served.extend(result.served)
    if len(served) != len(set(served)):
        reasons.append("duplicate_service_across_fleet")
    if require_all_customers:
        missing = sorted(set(instance.customer_ids()) - set(served))
        if missing:
            reasons.append(f"unserved:{','.join(missing)}")
    # Payload sanity: customer demand never exceeds capacity individually.
    for cust in instance.customers:
        if cust.demand > instance.vehicle_type.load_capacity + 1e-9:
            reasons.append(f"customer_demand_exceeds_capacity:{cust.id}")
    for node in instance.nodes.values():
        if node.kind is NodeKind.CHARGER and node.window.due < node.window.ready:
            reasons.append(f"bad_charger_window:{node.id}")
    return ValidationReport(
        feasible=not reasons,
        reasons=reasons,
        served=sorted(set(served)),
        total_distance=distance,
        total_charge_time=charge_time,
        vehicles_used=used,
    )
