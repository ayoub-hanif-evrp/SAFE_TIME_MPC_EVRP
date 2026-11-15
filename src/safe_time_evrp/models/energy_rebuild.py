"""Rebuild instance arc energies after changing vehicle consumption.

Schneider Euclidean instances bake ``energy = consumption_rate * distance`` into
each ``Arc`` at construction time. Changing only ``VehicleType.consumption_rate``
via ``dataclasses.replace`` leaves stale arc energies, which makes the plant log
``arc.energy`` while independent replay recomputes
``consumption_rate * hypot(dx, dy)`` — producing ``replay:travel_energy``.
"""

from __future__ import annotations

from dataclasses import replace

from safe_time_evrp.models.instance import Arc, Instance, VehicleType


def rebuild_arcs_for_vehicle_type(instance: Instance, vehicle_type: VehicleType) -> Instance:
    """Return a copy whose arc energies/travel times match ``vehicle_type``."""
    new_arcs: dict[tuple[str, str], Arc] = {}
    for (origin, dest), arc in instance.arcs.items():
        energy = vehicle_type.consumption_rate * arc.distance
        travel = arc.distance / vehicle_type.velocity if vehicle_type.velocity > 0 else arc.travel_time
        new_arcs[(origin, dest)] = replace(arc, energy=energy, travel_time=travel)
    return replace(instance, vehicle_type=vehicle_type, arcs=new_arcs)


def infinite_battery_instance(instance: Instance) -> Instance:
    """Consistent energy-relaxation: zero consumption and huge capacity, arcs rebuilt."""
    vt = instance.vehicle_type
    fat = VehicleType(
        battery_capacity=1e9,
        load_capacity=vt.load_capacity,
        consumption_rate=0.0,
        inverse_recharge_rate=vt.inverse_recharge_rate,
        velocity=vt.velocity,
        recharge_policy=vt.recharge_policy,
    )
    rebuilt = rebuild_arcs_for_vehicle_type(instance, fat)
    return replace(rebuilt, name=instance.name + "_infbat")
