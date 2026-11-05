"""Project paths. Raw benchmark files are local and are not committed."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def raw_dir() -> Path:
    return project_root() / "data" / "raw"


def manifest_path() -> Path:
    return project_root() / "data" / "manifests" / "source_manifest.json"


def schneider_dir() -> Path:
    return raw_dir() / "schneider_evrptw"


def arc_dir() -> Path:
    return raw_dir() / "evrptw_arc"


def kuleuven_dir() -> Path:
    return raw_dir() / "kuleuven_bev"
