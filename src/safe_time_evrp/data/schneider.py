"""Parser for the Schneider, Stenger and Goeke (2014) instance files.

The deposited readme defines Euclidean distances, constant speed, energy
``r * distance``, and recharge time ``g`` per unit of energy. Those rules are
applied here and recorded on the instance. They are benchmark units, not kWh.
"""

from __future__ import annotations

import re
from pathlib import Path

from safe_time_evrp.models.instance import (
    Instance,
    Node,
    NodeKind,
    TimeWindow,
    VehicleType,
    build_euclidean_instance,
)

_KIND = {"d": NodeKind.DEPOT, "c": NodeKind.CUSTOMER, "f": NodeKind.CHARGER}
_PARAM = re.compile(r"^([QCrgv])\b.*?/([+-]?(?:\d+(?:\.\d*)?|\.\d+))/\s*$")

ASSUMPTIONS = (
    "Distances are Euclidean, as stated by the deposited Schneider readme.",
    "Travel time is distance divided by the constant velocity v.",
    "Arc energy is r times distance and does not depend on payload.",
    "Energy and time use the benchmark's own units, not measured kWh or kilometres.",
    "The 2014 model recharges to the battery capacity. Partial recharge is a separate policy.",
    "Station capacity is not defined by the benchmark and is left unconstrained.",
    "A hard window constrains the start of service. Waiting is allowed. Service may end after the due time.",
    "Depot handling time is the depot service time in the file (zero in the deposited instances).",
)


def parse_schneider_text(text: str, name: str, source_name: str) -> Instance:
    nodes: list[Node] = []
    params: dict[str, float] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.lower().startswith("stringid"):
            continue
        match = _PARAM.match(line)
        if match:
            params[match.group(1)] = float(match.group(2))
            continue
        parts = line.split()
        if len(parts) != 8 or parts[1] not in _KIND:
            raise ValueError(f"{name}: unrecognized line: {line}")
        nodes.append(
            Node(
                id=parts[0],
                kind=_KIND[parts[1]],
                x=float(parts[2]),
                y=float(parts[3]),
                demand=float(parts[4]),
                window=TimeWindow(float(parts[5]), float(parts[6])),
                service_time=float(parts[7]),
            )
        )
    missing = {"Q", "C", "r", "g", "v"} - set(params)
    if missing:
        raise ValueError(f"{name}: missing vehicle parameters {sorted(missing)}")
    vehicle = VehicleType(
        battery_capacity=params["Q"],
        load_capacity=params["C"],
        consumption_rate=params["r"],
        inverse_recharge_rate=params["g"],
        velocity=params["v"],
        recharge_policy="full",
    )
    return build_euclidean_instance(
        name,
        nodes,
        vehicle,
        source_format="schneider_2014",
        source_name=source_name,
        assumptions=ASSUMPTIONS,
        station_capacity=None,
        metadata={
            "battery_symbol": "Q",
            "load_symbol": "C",
            "consumption_symbol": "r",
            "inverse_recharge_symbol": "g",
            "velocity_symbol": "v",
        },
    )


def parse_schneider_file(path: Path) -> Instance:
    return parse_schneider_text(path.read_text(encoding="utf-8"), path.stem, str(path))


def iter_instance_files(extracted_root: Path) -> list[Path]:
    files = [path for path in extracted_root.rglob("*.txt") if path.name.lower() != "readme.txt"]
    return sorted(files, key=lambda path: path.name.lower())
