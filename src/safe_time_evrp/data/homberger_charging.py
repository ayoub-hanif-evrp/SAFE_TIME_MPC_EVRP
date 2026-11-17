"""Homberger 1000-customer EVRPTW with heterogeneous charging stations (Zenodo).

Active dataset #3 (scalability appendix). Variant A keeps original time windows.
"""

from __future__ import annotations

import math
from pathlib import Path

from safe_time_evrp.data.paths import raw_dir
from safe_time_evrp.models.instance import Arc, Instance, Node, NodeKind, TimeWindow, VehicleType


def homberger_root() -> Path:
    base = raw_dir() / "evrptw_homberger_charging" / "EVRPTW_ChargingStations_Dataset"
    if not base.is_dir():
        raise FileNotFoundError(f"Homberger charging dataset not found at {base}")
    return base


def list_variant_a_instances(*, limit: int | None = None) -> list[Path]:
    folder = homberger_root() / "variant_A_original_TW"
    files = sorted(folder.glob("*.txt"))
    if limit is not None:
        files = files[:limit]
    return files


def _euclid(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def parse_homberger_evrptw(
    path: Path,
    *,
    battery_capacity: float = 100.0,
    consumption_rate: float = 1.0,
    inverse_recharge_rate: float = 0.5,
    velocity: float = 1.0,
    load_capacity: float | None = None,
) -> Instance:
    """Parse an augmented Homberger+chargers .txt (stations appended, id > 1000)."""
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # Skip header-like lines until numeric customer/depot rows.
    rows: list[list[str]] = []
    for ln in lines:
        parts = ln.split()
        if len(parts) < 7:
            continue
        try:
            float(parts[1])
            float(parts[2])
        except ValueError:
            continue
        rows.append(parts)

    if not rows:
        raise ValueError(f"no node rows in {path}")

    # Standard Homberger: CUST NO. XCOORD YCOORD DEMAND READY TIME DUE DATE SERVICE TIME
    # First row is depot (cust 0).
    nodes: dict[str, Node] = {}
    depot_id = "D0"
    capacity = float(load_capacity) if load_capacity is not None else 200.0

    for parts in rows:
        cid = int(float(parts[0]))
        x, y = float(parts[1]), float(parts[2])
        demand = float(parts[3])
        ready, due = float(parts[4]), float(parts[5])
        service = float(parts[6])
        if cid == 0:
            nid = depot_id
            kind = NodeKind.DEPOT
        elif cid > 1000:
            nid = f"S{cid}"
            kind = NodeKind.CHARGER
            demand = 0.0
        else:
            nid = f"C{cid}"
            kind = NodeKind.CUSTOMER
        nodes[nid] = Node(nid, kind, x, y, demand, TimeWindow(ready, due), service)

    if depot_id not in nodes:
        raise ValueError(f"depot missing in {path}")

    # Vehicle capacity sometimes appears in a VEHICLE line; keep override default.
    for ln in lines:
        low = ln.lower()
        if "capacity" in low:
            toks = ln.replace(",", " ").split()
            for i, t in enumerate(toks):
                if t.lower().startswith("capacity") and i + 1 < len(toks):
                    try:
                        capacity = float(toks[i + 1])
                    except ValueError:
                        pass

    vt = VehicleType(
        battery_capacity=battery_capacity,
        load_capacity=capacity,
        consumption_rate=consumption_rate,
        inverse_recharge_rate=inverse_recharge_rate,
        velocity=velocity,
        recharge_policy="partial",
    )
    arcs: dict[tuple[str, str], Arc] = {}
    ids = list(nodes)
    for a in ids:
        na = nodes[a]
        for b in ids:
            if a == b:
                continue
            nb = nodes[b]
            dist = _euclid(na.x, na.y, nb.x, nb.y)
            travel = dist / velocity
            energy = consumption_rate * dist
            arcs[(a, b)] = Arc(
                a,
                b,
                dist,
                travel,
                energy,
                distance_definition="euclidean",
            )

    return Instance(
        name=path.stem,
        nodes=nodes,
        arcs=arcs,
        vehicle_type=vt,
        depot_id=depot_id,
        source_format="homberger_evrptw_charging_stations",
        source_name=str(path),
        assumptions=("nonlinear_piecewise_charge", "euclidean_travel"),
    )
