"""Independent route-replay feasibility pilot for Gate 3B (no new controller)."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.instance import Instance, NodeKind


@dataclass
class ReplayResult:
    feasible: bool
    final_soc: float
    charge_events: int
    min_soc: float
    reason: str = ""


def replay_route(
    instance: Instance,
    node_sequence: list[str],
    *,
    start_soc: float | None = None,
    charge_to_full_at_chargers: bool = True,
    enforce_windows: bool = True,
) -> ReplayResult:
    """Replay a fixed route with battery dynamics; independent of optimizers."""
    soc = instance.vehicle_type.battery_capacity if start_soc is None else start_soc
    min_soc = soc
    charge_events = 0
    time = 0.0
    for i in range(len(node_sequence) - 1):
        a, b = node_sequence[i], node_sequence[i + 1]
        if (a, b) not in instance.arcs:
            return ReplayResult(False, soc, charge_events, min_soc, f"missing arc {a}->{b}")
        arc = instance.arcs[(a, b)]
        if soc < arc.energy - 1e-9:
            return ReplayResult(False, soc, charge_events, min_soc, f"energy shortfall on {a}->{b}")
        soc -= arc.energy
        time += arc.travel_time
        min_soc = min(min_soc, soc)
        node = instance.nodes[b]
        if node.kind is NodeKind.CUSTOMER:
            ready, due = node.window.ready, node.window.due
            if enforce_windows and time > due + 1e-9:
                return ReplayResult(False, soc, charge_events, min_soc, f"late at {b}")
            if enforce_windows:
                time = max(time, ready) + node.service_time
            else:
                time += node.service_time
        if node.kind is NodeKind.CHARGER and charge_to_full_at_chargers:
            target = instance.vehicle_type.battery_capacity
            if soc < target - 1e-9:
                delta = target - soc
                time += instance.vehicle_type.inverse_recharge_rate * delta
                soc = target
                charge_events += 1
    return ReplayResult(True, soc, charge_events, min_soc)


def nearest_neighbor_route(instance: Instance) -> list[str]:
    depot = instance.depot_id
    remaining = set(instance.customer_ids())
    route = [depot]
    cur = depot
    while remaining:
        nxt = min(remaining, key=lambda c: instance.arcs[(cur, c)].distance)
        route.append(nxt)
        remaining.remove(nxt)
        cur = nxt
    route.append(depot)
    return route


def route_with_forced_midpoint_charge(instance: Instance, base: list[str]) -> list[str] | None:
    chargers = instance.charger_ids()
    if not chargers or len(base) < 4:
        return None
    mid = len(base) // 2
    station = min(chargers, key=lambda s: instance.arcs[(base[mid - 1], s)].distance)
    return base[:mid] + [station] + base[mid:]


def tour_energy(instance: Instance, route: list[str]) -> float:
    return sum(instance.arcs[(route[i], route[i + 1])].energy for i in range(len(route) - 1))


def pilot_contrast(instance: Instance) -> dict:
    """Compare energy vs window binding for NN and NN+charge under the vehicle."""
    base = nearest_neighbor_route(instance)
    energy = tour_energy(instance, base)
    q = instance.vehicle_type.battery_capacity
    base_full = replay_route(instance, base, charge_to_full_at_chargers=False, enforce_windows=True)
    base_energy = replay_route(instance, base, charge_to_full_at_chargers=False, enforce_windows=False)
    charged_seq = route_with_forced_midpoint_charge(instance, base)
    charged_energy = (
        replay_route(instance, charged_seq, charge_to_full_at_chargers=True, enforce_windows=False)
        if charged_seq
        else None
    )
    charged_full = (
        replay_route(instance, charged_seq, charge_to_full_at_chargers=True, enforce_windows=True)
        if charged_seq
        else None
    )
    energy_binds = energy > q + 1e-9
    charge_rescues_energy = (not base_energy.feasible) and (charged_energy is not None and charged_energy.feasible)
    return {
        "instance": instance.name,
        "n_customers": len(instance.customers),
        "n_chargers": len(instance.chargers),
        "vehicle": instance.metadata.get("vehicle_config", instance.vehicle_type.battery_capacity),
        "nn_route": base,
        "nn_tour_energy": energy,
        "battery_Q": q,
        "energy_exceeds_Q": energy_binds,
        "nn_energy_only_feasible": base_energy.feasible,
        "nn_full_feasible": base_full.feasible,
        "nn_full_reason": base_full.reason,
        "nn_plus_charge_energy_feasible": None if charged_energy is None else charged_energy.feasible,
        "nn_plus_charge_full_feasible": None if charged_full is None else charged_full.feasible,
        "charge_events": None if charged_energy is None else charged_energy.charge_events,
        "battery_changes_energy_decision": charge_rescues_energy
        or (energy_binds and charged_energy is not None and charged_energy.feasible),
        # Backward-compatible alias used by early tests (full TW+energy).
        "nn_feasible_without_charge": base_full.feasible,
        "nn_plus_charge_feasible": None if charged_full is None else charged_full.feasible,
        "battery_changes_decision": (not base_full.feasible) and (charged_full is not None and charged_full.feasible),
    }
