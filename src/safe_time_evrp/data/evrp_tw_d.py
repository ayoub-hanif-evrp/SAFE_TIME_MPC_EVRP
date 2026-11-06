"""Parser for EVRP-TW-D (Zenodo 10.5281/zenodo.18529191).

Important Gate 3B finding
-------------------------
Zenodo metadata describes OSM/TIGER road networks and ``source_data`` /
``eval_standard_20`` territories. The published archive
``EVRP-TW-D-B-v1.0.tar.gz`` (MD5 verified) instead contains
``dataset/{anchored,unanchored}/Cus_*`` Solomon text + pickles whose
``env['dist_fun']`` is ``2-norm``. There are **no** road-edge tables in the
archive. Distances are therefore loaded as the release's own 2-norm metric and
labeled ``evrp_tw_d_2norm_source`` — never silently claimed as road-network km.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from safe_time_evrp.models.instance import Arc, Instance, Node, NodeKind, TimeWindow, VehicleType

ARCHIVE_NAME = "EVRP-TW-D-B-v1.0.tar.gz"
RECORD_VERSION = "v1.1"
PUBLISHED_MD5 = "7cc5ddd617dff8792b167f45ab7e4ed3"
LOCAL_SHA256 = "02da7522652daf3a1a00211a84e984f714002b3e200cf2f860b5a66376bc9fcb"
EXPECTED_SIZE = 527733122


@dataclass(frozen=True)
class VehicleConfig:
    name: str
    battery_capacity: float
    consumption_rate: float
    inverse_recharge_rate: float
    load_capacity: float
    velocity: float

    def as_vehicle_type(self) -> VehicleType:
        return VehicleType(
            battery_capacity=self.battery_capacity,
            load_capacity=self.load_capacity,
            consumption_rate=self.consumption_rate,
            inverse_recharge_rate=self.inverse_recharge_rate,
            velocity=self.velocity,
            recharge_policy="partial",
        )


# Versioned pilot overrides (fraction of instance-native battery).
PILOT_BATTERY_FRACTIONS = (1.0, 0.5, 0.25, 0.125)


def extract_root(raw_dir: Path) -> Path:
    candidates = [
        raw_dir / "extract" / "dataset",
        raw_dir / "dataset",
        raw_dir / "extract",
    ]
    for path in candidates:
        if (path / "anchored").is_dir() or (path / "unanchored").is_dir():
            return path
    raise FileNotFoundError(f"EVRP-TW-D dataset root not found under {raw_dir}")


def list_solomon_files(root: Path, *, split: str = "anchored", scale: str = "Cus_5") -> list[Path]:
    folder = root / split / scale / "solomon"
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    return sorted(folder.glob("solomon_dataset_*.txt"))


def _param(text: str, name: str) -> float:
    match = re.search(rf"{re.escape(name)}\s+/([0-9.]+)/", text)
    if not match:
        raise ValueError(f"missing parameter {name}")
    return float(match.group(1))


def parse_solomon_file(path: Path) -> Instance:
    """Parse one EVRP-TW-D Solomon-like text instance (2-norm distances)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    nodes: list[Node] = []
    for line in lines[1:]:
        if not line.strip() or line.startswith("Q ") or line.startswith("----"):
            if line.startswith("Q ") or line.startswith("----"):
                break
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        sid, typ = parts[0], parts[1]
        x, y, demand, ready, due, service = map(float, parts[2:8])
        if typ == "d":
            kind = NodeKind.DEPOT
        elif typ == "f":
            kind = NodeKind.CHARGER
        elif typ == "c":
            kind = NodeKind.CUSTOMER
        else:
            continue
        nodes.append(Node(sid, kind, x, y, demand, TimeWindow(ready, due), service))

    q = _param(text, "Q Vehicle fuel tank capacity")
    c = _param(text, "C Vehicle load capacity")
    r = _param(text, "r fuel consumption rate")
    g = _param(text, "g inverse refueling rate")
    v = _param(text, "v average Velocity")
    vehicle = VehicleType(q, c, r, g, v, recharge_policy="partial")

    depots = [n for n in nodes if n.kind is NodeKind.DEPOT]
    if len(depots) != 1:
        raise ValueError(f"{path.name} has {len(depots)} depots")
    arcs: dict[tuple[str, str], Arc] = {}
    for a in nodes:
        for b in nodes:
            if a.id == b.id:
                continue
            dist = math.hypot(a.x - b.x, a.y - b.y)
            arcs[(a.id, b.id)] = Arc(
                origin=a.id,
                destination=b.id,
                distance=dist,
                travel_time=dist / v,
                energy=r * dist,
                distance_definition="evrp_tw_d_2norm_source",
            )
    return Instance(
        name=path.stem,
        nodes={n.id: n for n in nodes},
        arcs=arcs,
        vehicle_type=vehicle,
        depot_id=depots[0].id,
        source_format="evrp_tw_d_solomon",
        source_name="EVRP-TW-D Geo-AC-v1.1 archive (2-norm)",
        assumptions=(
            "distance=evrp_tw_d_2norm_source",
            "zenodo_metadata_claimed_road_networks_absent_from_archive",
        ),
        metadata={"path": str(path), "split_scale": str(path.parent.parent.name)},
    )


def with_battery_fraction(instance: Instance, fraction: float, label: str) -> Instance:
    if not 0 < fraction <= 1:
        raise ValueError("fraction must be in (0,1]")
    vt = instance.vehicle_type
    vehicle = VehicleType(
        battery_capacity=vt.battery_capacity * fraction,
        load_capacity=vt.load_capacity,
        consumption_rate=vt.consumption_rate,
        inverse_recharge_rate=vt.inverse_recharge_rate,
        velocity=vt.velocity,
        recharge_policy=vt.recharge_policy,
    )
    return Instance(
        name=f"{instance.name}|bat={label}",
        nodes=instance.nodes,
        arcs={
            key: Arc(
                origin=arc.origin,
                destination=arc.destination,
                distance=arc.distance,
                travel_time=arc.travel_time,
                energy=arc.energy,
                distance_definition=arc.distance_definition,
            )
            for key, arc in instance.arcs.items()
        },
        vehicle_type=vehicle,
        depot_id=instance.depot_id,
        source_format=instance.source_format,
        source_name=instance.source_name,
        assumptions=instance.assumptions + (f"battery_fraction={fraction}",),
        metadata={**instance.metadata, "vehicle_config": label},
    )


def summarize_extract(root: Path) -> dict:
    anchored = root / "anchored"
    scales = sorted(p.name for p in anchored.iterdir() if p.is_dir()) if anchored.is_dir() else []
    counts = {}
    for scale in scales:
        sol = anchored / scale / "solomon"
        counts[scale] = len(list(sol.glob("*.txt"))) if sol.is_dir() else 0
    return {
        "root": str(root),
        "record_version": RECORD_VERSION,
        "archive_name": ARCHIVE_NAME,
        "published_md5": PUBLISHED_MD5,
        "local_sha256": LOCAL_SHA256,
        "expected_size": EXPECTED_SIZE,
        "layout": "anchored/unanchored Cus_* solomon+pickle",
        "distance_in_release": "2-norm (env.dist_fun)",
        "road_network_files_present": False,
        "anchored_scales": scales,
        "anchored_solomon_counts": counts,
    }
