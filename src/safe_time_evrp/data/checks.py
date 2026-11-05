"""Structural checks for a normalized instance. These do not solve a route."""

from __future__ import annotations

import math

from safe_time_evrp.models.instance import Instance, NodeKind


def validate_instance(instance: Instance) -> dict[str, object]:
    errors: list[str] = []
    customers = instance.customers
    chargers = instance.chargers
    if instance.depot_id not in instance.nodes:
        errors.append("missing depot")
    if sum(node.kind is NodeKind.DEPOT for node in instance.nodes.values()) != 1:
        errors.append("depot count is not 1")
    if not customers:
        errors.append("no customers")
    if not chargers:
        errors.append("no charging stations")
    ids = list(instance.nodes)
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids")
    expected_arcs = len(ids) * (len(ids) - 1)
    if len(instance.arcs) != expected_arcs:
        errors.append(f"arc count {len(instance.arcs)} != {expected_arcs}")
    missing_reverse = 0
    asymmetric = 0
    unreachable = 0
    for (origin, dest), arc in instance.arcs.items():
        if origin == dest:
            errors.append(f"self arc {origin}")
        if (dest, origin) not in instance.arcs:
            missing_reverse += 1
        else:
            reverse = instance.arcs[(dest, origin)]
            if abs(reverse.distance - arc.distance) > 1e-9 or abs(reverse.energy - arc.energy) > 1e-9:
                asymmetric += 1
        if arc.distance < -1e-9 or arc.travel_time < -1e-9 or arc.energy < -1e-9:
            errors.append(f"negative arc attribute {origin}->{dest}")
        if arc.energy > instance.vehicle_type.battery_capacity + 1e-9:
            unreachable += 1
        if instance.source_format == "schneider_2014":
            a = instance.node(origin)
            b = instance.node(dest)
            distance = math.hypot(a.x - b.x, a.y - b.y)
            if abs(distance - arc.distance) > 1e-6:
                errors.append(f"distance is not Euclidean for {origin}->{dest}")
            expected_energy = instance.vehicle_type.consumption_rate * distance
            expected_time = distance / instance.vehicle_type.velocity
            if abs(expected_energy - arc.energy) > 1e-6:
                errors.append(f"energy is not r*distance for {origin}->{dest}")
            if abs(expected_time - arc.travel_time) > 1e-6:
                errors.append(f"travel time is not distance/v for {origin}->{dest}")
    for node in instance.nodes.values():
        if node.window.due < node.window.ready:
            errors.append(f"invalid window {node.id}")
        if node.service_time < 0 or node.demand < 0:
            errors.append(f"negative demand or service {node.id}")
        if node.kind is not NodeKind.CUSTOMER and node.demand != 0:
            errors.append(f"non-customer {node.id} has demand")
    if instance.vehicle_type.inverse_recharge_rate <= 0:
        errors.append("non-positive recharge time coefficient")
    return {
        "name": instance.name,
        "customers": len(customers),
        "chargers": len(chargers),
        "depots": 1 if not errors else sum(n.kind is NodeKind.DEPOT for n in instance.nodes.values()),
        "arcs": len(instance.arcs),
        "directed": True,
        "missing_reverse_arcs": missing_reverse,
        "asymmetric_arcs": asymmetric,
        "arcs_exceeding_battery": unreachable,
        "battery_capacity": instance.vehicle_type.battery_capacity,
        "load_capacity": instance.vehicle_type.load_capacity,
        "consumption_rate": instance.vehicle_type.consumption_rate,
        "inverse_recharge_rate": instance.vehicle_type.inverse_recharge_rate,
        "velocity": instance.vehicle_type.velocity,
        "recharge_policy": instance.vehicle_type.recharge_policy,
        "station_capacity": instance.station_capacity,
        "errors": errors,
        "ok": not errors,
    }
