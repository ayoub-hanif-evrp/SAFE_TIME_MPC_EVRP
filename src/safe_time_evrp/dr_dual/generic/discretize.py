"""Finite SOC/time discretization for generic exact DP labels."""

from __future__ import annotations


def time_bin(t: float, *, dt: float = 1.0) -> int:
    return int(t // dt)


def soc_bin(soc: float, *, ds: float = 0.5) -> int:
    return int(soc // ds)


def resource_label(
    vehicle_id: str,
    node: str,
    time: float,
    soc: float,
    commitments: frozenset[str],
    info_set: frozenset[float],
    *,
    dt: float = 1.0,
    ds: float = 0.5,
) -> tuple:
    return (
        vehicle_id,
        node,
        time_bin(time, dt=dt),
        soc_bin(soc, ds=ds),
        tuple(sorted(commitments)),
        tuple(sorted(info_set)),
    )
