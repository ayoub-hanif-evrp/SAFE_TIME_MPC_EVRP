"""Adapter for an EVRPTW-ARC table if a real file is present.

The Zenodo record consulted for this project did not expose downloadable files.
This module does not invent road attributes. It reads a CSV only when every
required column is present, and it does not convert slopes into kWh.
"""

from __future__ import annotations

import csv
from pathlib import Path

REQUIRED_COLUMNS = (
    "from",
    "to",
    "distance_km",
    "time_h",
    "slope_mean_pct",
    "slope_max_pct",
    "elevation_gain_km",
    "elevation_loss_km",
    "road_type",
)


class ArcDatasetUnavailable(FileNotFoundError):
    """Raised when no official ARC file is on disk."""


def load_arc_table(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ArcDatasetUnavailable(f"no ARC table at {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = [column for column in REQUIRED_COLUMNS if column not in columns]
        if missing:
            raise ValueError(f"{path} is missing ARC columns {missing}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"{path} has no arc rows")
    return rows
