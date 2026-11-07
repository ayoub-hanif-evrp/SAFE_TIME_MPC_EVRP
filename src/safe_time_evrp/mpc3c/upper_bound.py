"""Offline service upper bounds for Gate 3F regime diagnostics.

These are constructive / optimistic bounds under nominal physics — not certificates
of online optimality.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance, Node, TimeWindow
from safe_time_evrp.models.state import Observation
from safe_time_evrp.optimization.insertion import construct_routes
from safe_time_evrp.testbed.constructor import make_observation


@dataclass(frozen=True)
class UpperBoundReport:
    n_customers: int
    n_announced: int
    n_a_priori_impossible: int
    static_constructive_served: int
    static_service_rate: float
    a_priori_impossible_ids: tuple[str, ...]
    notes: tuple[str, ...]


def a_priori_impossible(
    instance: Instance,
    releases: list[tuple[str, float]],
) -> list[str]:
    """Customers whose announcement leaves no positive slack before due."""
    bad: list[str] = []
    for cid, announce in releases:
        node = instance.node(cid)
        earliest_start = max(float(announce), float(node.window.ready))
        if earliest_start > float(node.window.due) + 1e-12:
            bad.append(cid)
            continue
        try:
            arc = instance.arc(instance.depot_id, cid)
            arrive = max(float(announce), 0.0) + float(arc.travel_time)
            start = max(arrive, float(node.window.ready))
            if start > float(node.window.due) + 1e-12:
                bad.append(cid)
        except KeyError:
            bad.append(cid)
    return sorted(set(bad))


def _instance_with_announcement_ready(
    instance: Instance,
    releases: list[tuple[str, float]],
) -> Instance:
    """Clone instance so earliest service is max(window.ready, announcement)."""
    announce = {cid: float(t) for cid, t in releases}
    nodes = dict(instance.nodes)
    for cid, t_ann in announce.items():
        node = instance.node(cid)
        ready = max(float(node.window.ready), t_ann)
        due = float(node.window.due)
        if due < ready:
            # Keep mathematically valid window; a_priori_impossible already flags these.
            due = ready
        nodes[cid] = Node(
            node.id,
            node.kind,
            node.x,
            node.y,
            node.demand,
            TimeWindow(ready, due),
            node.service_time,
        )
    return Instance(
        name=instance.name + "+announce_ready",
        nodes=nodes,
        arcs=instance.arcs,
        vehicle_type=instance.vehicle_type,
        depot_id=instance.depot_id,
        source_format=instance.source_format,
        source_name=instance.source_name,
        assumptions=instance.assumptions + ("ready_max_of_window_and_announcement",),
        station_capacity=instance.station_capacity,
        metadata=dict(instance.metadata),
    )


def offline_service_upper_bound(
    instance: Instance,
    releases: list[tuple[str, float]],
    *,
    fleet_size: int,
) -> UpperBoundReport:
    """Optimistic constructive bound respecting announcement-aware ready times.

    All announced IDs are known to the planner, but service cannot start before
    max(window.ready, announcement). This avoids a vacuous 100% bound that ignores
    late announcements.
    """
    announced = [cid for cid, _ in releases]
    impossible = a_priori_impossible(instance, releases)
    ban = set(impossible)
    eligible = [cid for cid in announced if cid not in ban]
    plant = _instance_with_announcement_ready(instance, releases)
    base = make_observation(plant, fleet_size, start_time=0.0)
    obs = Observation(
        0.0,
        base.vehicles,
        tuple(eligible),
        (),
        (),
        tuple(impossible),
        (),
        (),
    )
    dues = [float(plant.node(c).window.due) for c in eligible] or [1.0]
    horizon = max(dues) + 1.0
    plan = construct_routes(plant, obs, horizon=horizon, energy=NominalLinearEnergy())
    served = len(set(plan.planned_service)) if plan.feasible_commitments else 0
    return UpperBoundReport(
        n_customers=len(instance.customer_ids()),
        n_announced=len(announced),
        n_a_priori_impossible=len(impossible),
        static_constructive_served=served,
        static_service_rate=served / max(len(announced), 1),
        a_priori_impossible_ids=tuple(impossible),
        notes=(
            "static_constructive_with_announcement_ready",
            "nominal_energy_only",
            f"horizon={horizon}",
            f"fleet_size={fleet_size}",
        ),
    )


def is_middle_regime(report: UpperBoundReport, *, low: float = 0.40, high: float = 0.80) -> bool:
    """True when optimistic bound sits in a non-extreme service band."""
    if report.n_announced <= 0:
        return False
    if report.n_a_priori_impossible / report.n_announced > 0.5:
        return False
    return low - 1e-12 <= report.static_service_rate <= high + 1e-12
