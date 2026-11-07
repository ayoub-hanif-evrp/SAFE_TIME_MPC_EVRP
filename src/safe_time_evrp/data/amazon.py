"""Amazon Last Mile subset loader with modeled electrification (Gate 3C).

Travel times come from the published matrices. Distances used for energy are
``travel_time_h * assumed_speed_kmh`` (operational proxy), never Euclidean
haversine between stop coordinates.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from safe_time_evrp.models.instance import Arc, Instance, Node, NodeKind, TimeWindow, VehicleType


@dataclass(frozen=True)
class ElectrificationConfig:
    name: str
    battery_kwh: float
    consumption_kwh_per_km: float
    charge_kw: float
    assumed_speed_kmh: float
    load_capacity: float
    # Soft day horizon in hours from departure.
    day_horizon_h: float = 12.0


# Order-of-magnitude light cargo EV inspired by ESOGU-ML5EV class.
ESOGU_LIGHT_CARGO_V1 = ElectrificationConfig(
    name="esogu_light_cargo_v1",
    battery_kwh=40.0,
    consumption_kwh_per_km=0.15,
    charge_kw=11.0,
    assumed_speed_kmh=30.0,
    load_capacity=1e9,  # Amazon capacity is volumetric; ignore tight payload for this pilot
)


def subset_dir() -> Path:
    return Path("data/raw/amazon_last_mile/subset")


def list_route_ids(directory: Path | None = None) -> list[str]:
    path = (directory or subset_dir()) / "route_data_subset.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted(payload.keys())


def _parse_window_hours(start, end, day_horizon: float) -> TimeWindow:
    # Many Amazon windows are null; use full day then.
    if start is None or (isinstance(start, float) and math.isnan(start)):
        return TimeWindow(0.0, day_horizon)
    if end is None or (isinstance(end, float) and math.isnan(end)):
        return TimeWindow(0.0, day_horizon)
    # Treat as relative within the day: if strings, open windows to day horizon.
    # We do not use delivery completion times as online information.
    return TimeWindow(0.0, day_horizon)


def load_amazon_route(
    route_id: str,
    *,
    directory: Path | None = None,
    electrification: ElectrificationConfig = ESOGU_LIGHT_CARGO_V1,
    max_customers: int = 12,
    add_depot_charger: bool = True,
) -> Instance:
    """Build an Instance for one Amazon historical route with modeled EV physics."""
    base = directory or subset_dir()
    routes = json.loads((base / "route_data_subset.json").read_text(encoding="utf-8"))
    packages = json.loads((base / "package_data_subset.json").read_text(encoding="utf-8"))
    travel = json.loads((base / "travel_times_subset.json").read_text(encoding="utf-8"))
    if route_id not in routes or route_id not in travel:
        raise KeyError(route_id)
    route = routes[route_id]
    tt = travel[route_id]
    pkg = packages.get(route_id, {})

    station_ids = [sid for sid, stop in route["stops"].items() if stop["type"] == "Station"]
    if len(station_ids) != 1:
        raise ValueError(f"{route_id} has {len(station_ids)} stations")
    depot_id = station_ids[0]
    dropoffs = sorted(sid for sid, stop in route["stops"].items() if stop["type"] == "Dropoff")
    dropoffs = dropoffs[:max_customers]

    nodes: list[Node] = []
    depot_stop = route["stops"][depot_id]
    nodes.append(
        Node(
            depot_id,
            NodeKind.DEPOT,
            float(depot_stop["lat"]),
            float(depot_stop["lng"]),
            0.0,
            TimeWindow(0.0, electrification.day_horizon_h),
            0.0,
        )
    )
    if add_depot_charger:
        # Synthetic charger colocated at depot (documented assumption).
        nodes.append(
            Node(
                f"{depot_id}_CHG",
                NodeKind.CHARGER,
                float(depot_stop["lat"]),
                float(depot_stop["lng"]),
                0.0,
                TimeWindow(0.0, electrification.day_horizon_h),
                0.0,
            )
        )

    for sid in dropoffs:
        stop = route["stops"][sid]
        service = 0.0
        ready, due = 0.0, electrification.day_horizon_h
        for _pid, meta in pkg.get(sid, {}).items():
            service = max(service, float(meta.get("planned_service_time_seconds") or 0.0) / 3600.0)
            tw = meta.get("time_window") or {}
            window = _parse_window_hours(
                tw.get("start_time_utc"), tw.get("end_time_utc"), electrification.day_horizon_h
            )
            ready = window.ready
            due = window.due
        nodes.append(
            Node(
                sid,
                NodeKind.CUSTOMER,
                float(stop["lat"]),
                float(stop["lng"]),
                0.01,
                TimeWindow(ready, due),
                service,
            )
        )

    ids = [n.id for n in nodes]

    # Map charger id travel times: same as depot.
    def tt_seconds(a: str, b: str) -> float:
        aa = depot_id if a.endswith("_CHG") else a
        bb = depot_id if b.endswith("_CHG") else b
        if aa not in tt or bb not in tt[aa]:
            raise KeyError(f"missing travel time {aa}->{bb}")
        return float(tt[aa][bb])

    vehicle = VehicleType(
        battery_capacity=electrification.battery_kwh,
        load_capacity=electrification.load_capacity,
        consumption_rate=electrification.consumption_kwh_per_km,
        inverse_recharge_rate=1.0 / electrification.charge_kw,
        velocity=electrification.assumed_speed_kmh,
        recharge_policy="full",
    )
    arcs: dict[tuple[str, str], Arc] = {}
    for a in ids:
        for b in ids:
            if a == b:
                continue
            seconds = tt_seconds(a, b)
            hours = seconds / 3600.0
            dist_km = hours * electrification.assumed_speed_kmh
            energy = electrification.consumption_kwh_per_km * dist_km
            arcs[(a, b)] = Arc(
                origin=a,
                destination=b,
                distance=dist_km,
                travel_time=hours,
                energy=energy,
                distance_definition="amazon_travel_time_proxy",
                distance_km=dist_km,
                travel_time_h=hours,
            )

    return Instance(
        name=route_id,
        nodes={n.id: n for n in nodes},
        arcs=arcs,
        vehicle_type=vehicle,
        depot_id=depot_id,
        source_format="amazon_last_mile_subset",
        source_name="ALMRRC2021 training subset (electrified model)",
        assumptions=(
            f"electrification={electrification.name}",
            "distance=travel_time_h*assumed_speed_kmh",
            "not_observed_ev",
            "depot_colocated_charger" if add_depot_charger else "no_extra_charger",
            f"max_customers={max_customers}",
        ),
        metadata={"route_id": route_id, "station_code": str(route.get("station_code"))},
    )
