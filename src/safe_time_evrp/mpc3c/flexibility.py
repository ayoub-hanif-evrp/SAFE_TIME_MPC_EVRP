"""Explicit flexibility terminal approximation for Gate 3C (not a black box)."""

from __future__ import annotations

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Anchor, Visit


def reachable_chargers(instance: Instance, anchor: Anchor, energy: NominalLinearEnergy | None = None) -> int:
    model = energy or NominalLinearEnergy()
    count = 0
    for sid in instance.charger_ids():
        try:
            arc = instance.arc(anchor.node, sid)
        except KeyError:
            continue
        used = model.travel_energy(instance, arc, soc=anchor.soc, load=anchor.load)
        if anchor.soc + 1e-9 >= used:
            count += 1
    return count


def insertion_flexibility(
    instance: Instance,
    anchor: Anchor,
    remaining_customers: list[str],
    *,
    energy: NominalLinearEnergy | None = None,
    limit: int = 12,
) -> int:
    """Count alternative next-customer insertions that remain energy+TW feasible alone."""
    model = energy or NominalLinearEnergy()
    ok = 0
    for cid in remaining_customers[:limit]:
        for variant in (
            [Visit(cid, "service")],
            *[[Visit(sid, "charge"), Visit(cid, "service")] for sid in instance.charger_ids()[:3]],
        ):
            result = evaluate_route(instance, anchor, variant, model)
            if result.feasible and cid in result.served:
                ok += 1
                break
    return ok


def flexibility_terminal_value(
    instance: Instance,
    anchor: Anchor,
    remaining_customers: list[str],
    *,
    w_soc: float = 0.05,
    w_charge: float = 0.5,
    w_insert: float = 1.0,
    w_remaining_penalty: float = 3.0,
) -> float:
    """Higher is better. Not equal to SOC alone."""
    q = instance.vehicle_type.battery_capacity
    soc_term = w_soc * (anchor.soc / q if q else 0.0)
    charge_term = w_charge * reachable_chargers(instance, anchor)
    insert_term = w_insert * insertion_flexibility(instance, anchor, remaining_customers)
    remain_pen = w_remaining_penalty * len(remaining_customers)
    return soc_term + charge_term + insert_term - remain_pen
