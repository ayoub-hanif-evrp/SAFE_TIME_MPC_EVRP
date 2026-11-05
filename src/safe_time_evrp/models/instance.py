"""Normalized EVRP instance.

Schneider et al. (2014) distances are Euclidean by the dataset readme. That is the
authoritative metric for those files, not a substitute for a road network. Road-network
fields stay empty unless a source actually provides them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class NodeKind(str, Enum):
    DEPOT = "depot"
    CUSTOMER = "customer"
    CHARGER = "charger"


@dataclass(frozen=True)
class TimeWindow:
    ready: float
    due: float

    def __post_init__(self) -> None:
        if self.due < self.ready:
            raise ValueError(f"time window due {self.due} precedes ready {self.ready}")


@dataclass(frozen=True)
class Node:
    id: str
    kind: NodeKind
    x: float
    y: float
    demand: float
    window: TimeWindow
    service_time: float


@dataclass(frozen=True)
class Arc:
    origin: str
    destination: str
    distance: float
    travel_time: float
    energy: float
    distance_definition: str
    # Optional road attributes. None means the source did not provide them.
    distance_km: float | None = None
    travel_time_h: float | None = None
    slope_mean_pct: float | None = None
    slope_max_pct: float | None = None
    elevation_gain_km: float | None = None
    elevation_loss_km: float | None = None
    road_type: str | None = None
    speed_mean_kmh: float | None = None
    traffic_scenario: str | None = None
    temperature_c: float | None = None
    driving_style: str | None = None


@dataclass(frozen=True)
class VehicleType:
    battery_capacity: float
    load_capacity: float
    consumption_rate: float
    inverse_recharge_rate: float
    velocity: float
    # "full" is the Schneider (2014) scheme. "partial" uses the same linear rate.
    recharge_policy: str = "full"

    def __post_init__(self) -> None:
        if self.battery_capacity <= 0:
            raise ValueError("battery capacity must be positive")
        if self.load_capacity <= 0:
            raise ValueError("load capacity must be positive")
        if self.consumption_rate < 0:
            raise ValueError("consumption rate cannot be negative")
        if self.inverse_recharge_rate < 0:
            raise ValueError("inverse recharge rate cannot be negative")
        if self.velocity <= 0:
            raise ValueError("velocity must be positive")
        if self.recharge_policy not in {"full", "partial"}:
            raise ValueError("recharge policy must be 'full' or 'partial'")


@dataclass
class Instance:
    name: str
    nodes: dict[str, Node]
    arcs: dict[tuple[str, str], Arc]
    vehicle_type: VehicleType
    depot_id: str
    source_format: str
    source_name: str
    assumptions: tuple[str, ...] = ()
    # None: the benchmark does not constrain how many vehicles may charge at once.
    station_capacity: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def arc(self, origin: str, destination: str) -> Arc:
        return self.arcs[(origin, destination)]

    @property
    def customers(self) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind is NodeKind.CUSTOMER]

    @property
    def chargers(self) -> list[Node]:
        return [n for n in self.nodes.values() if n.kind is NodeKind.CHARGER]

    def customer_ids(self) -> list[str]:
        return sorted(n.id for n in self.customers)

    def charger_ids(self) -> list[str]:
        return sorted(n.id for n in self.chargers)

    def with_recharge_policy(self, policy: str) -> Instance:
        vehicle = VehicleType(
            battery_capacity=self.vehicle_type.battery_capacity,
            load_capacity=self.vehicle_type.load_capacity,
            consumption_rate=self.vehicle_type.consumption_rate,
            inverse_recharge_rate=self.vehicle_type.inverse_recharge_rate,
            velocity=self.vehicle_type.velocity,
            recharge_policy=policy,
        )
        return Instance(
            name=self.name,
            nodes=self.nodes,
            arcs=self.arcs,
            vehicle_type=vehicle,
            depot_id=self.depot_id,
            source_format=self.source_format,
            source_name=self.source_name,
            assumptions=self.assumptions + (f"recharge_policy={policy}",),
            station_capacity=self.station_capacity,
            metadata=dict(self.metadata),
        )


def euclidean(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def build_euclidean_instance(
    name: str,
    nodes: list[Node],
    vehicle_type: VehicleType,
    *,
    source_format: str,
    source_name: str,
    assumptions: tuple[str, ...] = (),
    station_capacity: int | None = None,
    metadata: dict[str, str] | None = None,
) -> Instance:
    """Complete directed graph. Both orientations are stored even when symmetric."""
    depots = [n for n in nodes if n.kind is NodeKind.DEPOT]
    if len(depots) != 1:
        raise ValueError(f"{name} has {len(depots)} depots; expected one")
    ids = [n.id for n in nodes]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{name} has duplicate node ids")
    node_map = {n.id: n for n in nodes}
    arcs: dict[tuple[str, str], Arc] = {}
    for origin in nodes:
        for dest in nodes:
            if origin.id == dest.id:
                continue
            distance = euclidean(origin.x, origin.y, dest.x, dest.y)
            arcs[(origin.id, dest.id)] = Arc(
                origin=origin.id,
                destination=dest.id,
                distance=distance,
                travel_time=distance / vehicle_type.velocity,
                energy=vehicle_type.consumption_rate * distance,
                distance_definition="euclidean_source_definition",
            )
    return Instance(
        name=name,
        nodes=node_map,
        arcs=arcs,
        vehicle_type=vehicle_type,
        depot_id=depots[0].id,
        source_format=source_format,
        source_name=source_name,
        assumptions=assumptions,
        station_capacity=station_capacity,
        metadata=metadata or {},
    )
