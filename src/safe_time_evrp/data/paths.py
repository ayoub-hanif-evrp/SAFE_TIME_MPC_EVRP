"""Project paths. Raw benchmark files are local and are not committed.

Active datasets (see ``data/ACTIVE_DATASETS.json``):
  schneider_evrptw, evrp_tw_d, evrptw_homberger_charging
"""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def raw_dir() -> Path:
    return project_root() / "data" / "raw"


def retired_dir() -> Path:
    return raw_dir() / "_retired"


def manifest_path() -> Path:
    return project_root() / "data" / "manifests" / "source_manifest.json"


def schneider_dir() -> Path:
    return raw_dir() / "schneider_evrptw"


def evrp_tw_d_dir() -> Path:
    return raw_dir() / "evrp_tw_d"


def homberger_charging_dir() -> Path:
    return raw_dir() / "evrptw_homberger_charging"


def arc_dir() -> Path:
    return retired_dir() / "evrptw_arc"


def kuleuven_dir() -> Path:
    return retired_dir() / "kuleuven_bev"


def lade_dir() -> Path:
    return retired_dir() / "lade"


def amazon_last_mile_dir() -> Path:
    return retired_dir() / "amazon_last_mile"


def esogu_dir() -> Path:
    return retired_dir() / "esogu_ml5ev"
