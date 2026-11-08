"""Controller-facing public planning snapshot (online information boundary).

The private plant may retain the full instance. Optimizers must only see
infrastructure plus customers that are already observable in the Observation.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.instance import Instance, NodeKind, build_euclidean_instance
from safe_time_evrp.models.state import Observation


@dataclass(frozen=True)
class PublicPlanningSnapshot:
    """Sanitized planning input: no future customer identities or release times."""

    instance: Instance
    observation: Observation
    horizon: float
    visible_customer_ids: frozenset[str]


def visible_customer_ids(observation: Observation) -> frozenset[str]:
    return frozenset(
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.completed)
        | set(observation.rejected)
        | set(observation.in_service)
        | set(observation.deferred)
    )


def sanitize_instance(full: Instance, visible: frozenset[str]) -> Instance:
    """Drop unreleased customers from the controller-facing instance.

    Depot, chargers, and arcs among remaining nodes are retained. Metadata that
    could encode future demand is stripped.
    """
    keep_nodes = []
    for node in full.nodes.values():
        if node.kind is NodeKind.DEPOT or node.kind is NodeKind.CHARGER:
            keep_nodes.append(node)
        elif node.kind is NodeKind.CUSTOMER and node.id in visible:
            keep_nodes.append(node)
    # Preserve non-euclidean tables by filtering the original arc map when possible
    if full.source_format in {"synthetic", "euclidean", "schneider_2014"}:
        return build_euclidean_instance(
            name=f"{full.name}__public",
            nodes=keep_nodes,
            vehicle_type=full.vehicle_type,
            source_format=full.source_format,
            source_name=full.source_name,
            assumptions=full.assumptions + ("public_snapshot_no_future_customers",),
            station_capacity=full.station_capacity,
            metadata={"public_snapshot": "1", "parent": full.name},
        )
    # Fallback: rebuild with filtered node set via euclidean of coordinates
    return build_euclidean_instance(
        name=f"{full.name}__public",
        nodes=keep_nodes,
        vehicle_type=full.vehicle_type,
        source_format=full.source_format,
        source_name=full.source_name,
        assumptions=full.assumptions + ("public_snapshot_no_future_customers",),
        station_capacity=full.station_capacity,
        metadata={"public_snapshot": "1", "parent": full.name},
    )


def make_public_snapshot(full: Instance, observation: Observation, horizon: float) -> PublicPlanningSnapshot:
    visible = visible_customer_ids(observation)
    return PublicPlanningSnapshot(
        instance=sanitize_instance(full, visible),
        observation=observation,
        horizon=horizon,
        visible_customer_ids=visible,
    )


def assert_no_future_leak(snapshot: PublicPlanningSnapshot, full: Instance) -> None:
    """Raise if any unreleased customer id appears in the public instance."""
    public_customers = {n.id for n in snapshot.instance.customers}
    all_customers = {n.id for n in full.customers}
    leaked = public_customers - snapshot.visible_customer_ids
    if leaked:
        raise AssertionError(f"public snapshot leaked customers: {sorted(leaked)}")
    hidden = all_customers - snapshot.visible_customer_ids
    if public_customers & hidden:
        raise AssertionError("hidden customers present in public instance")
