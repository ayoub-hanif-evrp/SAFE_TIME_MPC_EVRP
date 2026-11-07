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

# Gate 3D energy-active profile: consumption uplift at fixed 40 kWh (not ≤25% Q).
# Empirically, ≥0.5 kWh/km with ≥12 stops yields charge events on the subset
# while tours remain mostly serviceable under FleetSimulator.
ESOGU_ENERGY_ACTIVE_V1 = ElectrificationConfig(
    name="esogu_energy_active_v1",
    battery_kwh=40.0,
    consumption_kwh_per_km=0.50,
    charge_kw=11.0,
    assumed_speed_kmh=30.0,
    load_capacity=1e9,
    day_horizon_h=12.0,
)


def subset_dir() -> Path:
    return Path("data/raw/amazon_last_mile/subset")


def list_route_ids(directory: Path | None = None) -> list[str]:
    path = (directory or subset_dir()) / "route_data_subset.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return sorted(payload.keys())


def _is_missing(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _parse_utc_hours_from_departure(value, departure_epoch_h: float) -> float | None:
    """Parse Amazon UTC timestamp to hours relative to route departure."""
    if _is_missing(value):
        return None
    if isinstance(value, (int, float)):
        # Already numeric hours — treat as absolute day hours if small, else epoch-like.
        return float(value) - departure_epoch_h
    text = str(value).strip()
    # Formats observed in ALMRRC subset: "2018-07-27 16:00:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            from datetime import datetime

            dt = datetime.strptime(text, fmt)
            # Encode as hours since an arbitrary origin; departure uses the same origin.
            epoch_h = (dt - datetime(2018, 1, 1)).total_seconds() / 3600.0
            return epoch_h - departure_epoch_h
        except ValueError:
            continue
    return None


def _parse_window_hours(
    start,
    end,
    day_horizon: float,
    *,
    departure_epoch_h: float = 0.0,
) -> TimeWindow:
    """Honor UTC start/end when parseable; full-day only when NaN/missing."""
    ready = _parse_utc_hours_from_departure(start, departure_epoch_h)
    due = _parse_utc_hours_from_departure(end, departure_epoch_h)
    if ready is None and due is None:
        return TimeWindow(0.0, day_horizon)
    if ready is None:
        ready = 0.0
    if due is None:
        due = day_horizon
    # Clamp into the modeled operational day; keep ordering.
    ready = max(0.0, min(float(ready), day_horizon))
    due = max(ready, min(float(due), day_horizon))
    return TimeWindow(ready, due)


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

    # Departure epoch for relative windows (date + departure_time_utc).
    from datetime import datetime

    date_s = str(route.get("date_YYYY_MM_DD") or "2018-01-01")
    dep_s = str(route.get("departure_time_utc") or "00:00:00")
    try:
        departure_dt = datetime.strptime(f"{date_s} {dep_s}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            departure_dt = datetime.strptime(date_s, "%Y-%m-%d")
        except ValueError:
            departure_dt = datetime(2018, 1, 1)
    departure_epoch_h = (departure_dt - datetime(2018, 1, 1)).total_seconds() / 3600.0

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

    modeled_windows = 0
    observed_windows = 0
    for sid in dropoffs:
        stop = route["stops"][sid]
        service = 0.0
        ready, due = 0.0, electrification.day_horizon_h
        for _pid, meta in pkg.get(sid, {}).items():
            service = max(service, float(meta.get("planned_service_time_seconds") or 0.0) / 3600.0)
            tw = meta.get("time_window") or {}
            start_raw, end_raw = tw.get("start_time_utc"), tw.get("end_time_utc")
            if not _is_missing(start_raw) or not _is_missing(end_raw):
                observed_windows += 1
            window = _parse_window_hours(
                start_raw,
                end_raw,
                electrification.day_horizon_h,
                departure_epoch_h=departure_epoch_h,
            )
            ready = window.ready
            due = window.due
            if ready > 0.0 or due < electrification.day_horizon_h - 1e-9:
                modeled_windows += 1
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
            "windows=parsed_utc_when_present_else_full_day",
            f"observed_package_windows={observed_windows}",
            f"nontrivial_modeled_windows={modeled_windows}",
        ),
        metadata={
            "route_id": route_id,
            "station_code": str(route.get("station_code")),
            "departure_time_utc": dep_s,
            "date_YYYY_MM_DD": date_s,
            "observed_package_windows": str(observed_windows),
            "nontrivial_modeled_windows": str(modeled_windows),
            "electrification": electrification.name,
        },
    )
