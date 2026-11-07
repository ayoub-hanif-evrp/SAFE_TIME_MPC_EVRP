"""Multi-vehicle TW/energy/payload constructive solver for Gate 3C testbed seeds."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Anchor, Observation, VehicleView
from safe_time_evrp.optimization.insertion import InsertionPlan, construct_routes
from safe_time_evrp.testbed.validator import ValidationReport, validate_fleet_plan


@dataclass
class SeedResult:
    instance_name: str
    fleet_size: int
    plan: InsertionPlan | None
    validation: ValidationReport
    recharge_policy: str


def make_observation(instance: Instance, fleet_size: int, *, start_time: float = 0.0) -> Observation:
    soc = instance.vehicle_type.battery_capacity
    vehicles = []
    for i in range(fleet_size):
        anchor = Anchor(instance.depot_id, start_time, soc, 0.0, frozenset())
        vehicles.append(VehicleView(f"v{i}", "idle", instance.depot_id, soc, 0.0, (), anchor, None))
    customers = tuple(instance.customer_ids())
    return Observation(start_time, tuple(vehicles), customers, customers, (), (), (), ())


def construct_feasible_seed(
    instance: Instance,
    *,
    fleet_size: int,
    recharge_policy: str = "full",
    start_time: float = 0.0,
) -> SeedResult:
    """Build a fully validated multi-vehicle plan under native battery capacity."""
    inst = instance.with_recharge_policy(recharge_policy)
    obs = make_observation(inst, fleet_size, start_time=start_time)
    plan = construct_routes(inst, obs, horizon=1e9, energy=NominalLinearEnergy())
    routes = plan.routes if plan.feasible_commitments else {v.id: [] for v in obs.vehicles}
    # construct_routes finalizes with return visits when feasible.
    validation = validate_fleet_plan(
        inst,
        routes,
        start_time=start_time,
        require_all_customers=True,
    )
    if plan.feasible_commitments and set(plan.planned_service) != set(inst.customer_ids()):
        validation = ValidationReport(
            False,
            reasons=validation.reasons + ["incomplete_service_set"],
            served=validation.served,
            total_distance=validation.total_distance,
            total_charge_time=validation.total_charge_time,
            vehicles_used=validation.vehicles_used,
        )
    return SeedResult(
        instance_name=inst.name,
        fleet_size=fleet_size,
        plan=plan if validation.feasible else None,
        validation=validation,
        recharge_policy=recharge_policy,
    )


def find_minimal_fleet_seed(
    instance: Instance,
    *,
    max_fleet: int = 8,
    recharge_policy: str = "full",
) -> SeedResult:
    last = construct_feasible_seed(instance, fleet_size=1, recharge_policy=recharge_policy)
    for fleet in range(1, max_fleet + 1):
        last = construct_feasible_seed(instance, fleet_size=fleet, recharge_policy=recharge_policy)
        if last.validation.feasible:
            return last
    return last


def adaptive_charge_target(instance: Instance, soc: float, next_energy_need: float) -> float:
    """Charge amount chosen at station from observed SOC (Gate 3C contract)."""
    q = instance.vehicle_type.battery_capacity
    need = min(q, max(soc, next_energy_need))
    return need
