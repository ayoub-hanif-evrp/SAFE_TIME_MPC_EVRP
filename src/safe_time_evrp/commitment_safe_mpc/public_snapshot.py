"""Controller-facing public planning snapshot (online information boundary).

The private plant may retain the full instance. Optimizers must only see
infrastructure plus customers that are already observable in the Observation.

Sanitization **filters** original ``Arc`` records; it does not rebuild Euclidean
weights (preserves asymmetric / non-Euclidean physics).
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import Observation

# Strict allowlist — future-demand / private keys never pass through.
_PUBLIC_METADATA_ALLOWLIST = frozenset(
    {
        "public_snapshot",
        "parent",
        "suite",
        "adversarial",
    }
)


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
    """Drop unreleased customers; retain original arcs among remaining nodes."""
    keep_nodes = {}
    for node_id, node in full.nodes.items():
        if node.kind is NodeKind.DEPOT or node.kind is NodeKind.CHARGER:
            keep_nodes[node_id] = node
        elif node.kind is NodeKind.CUSTOMER and node.id in visible:
            keep_nodes[node_id] = node
    keep_ids = set(keep_nodes)
    arcs = {(o, d): arc for (o, d), arc in full.arcs.items() if o in keep_ids and d in keep_ids}
    meta = {k: v for k, v in full.metadata.items() if k in _PUBLIC_METADATA_ALLOWLIST}
    meta["public_snapshot"] = "1"
    meta["parent"] = full.name
    return Instance(
        name=f"{full.name}__public",
        nodes=keep_nodes,
        arcs=arcs,
        vehicle_type=full.vehicle_type,
        depot_id=full.depot_id,
        source_format=full.source_format,
        source_name=full.source_name,
        assumptions=full.assumptions + ("public_snapshot_no_future_customers", "arcs_filtered_not_rebuilt"),
        station_capacity=full.station_capacity,
        metadata=meta,
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
    leaked = public_customers - snapshot.visible_customer_ids
    if leaked:
        raise AssertionError(f"public snapshot leaked customers: {sorted(leaked)}")
    hidden = {n.id for n in full.customers} - snapshot.visible_customer_ids
    if public_customers & hidden:
        raise AssertionError("hidden customers present in public instance")
    bad = set(snapshot.instance.metadata) - _PUBLIC_METADATA_ALLOWLIST
    if bad:
        raise AssertionError(f"public metadata not allowlisted: {sorted(bad)}")
