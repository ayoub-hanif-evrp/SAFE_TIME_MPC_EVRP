"""Tiny discrete EVRP plant for exact policy enumeration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArcMode:
    """One travel realization. ``z`` counts against the residual budget."""

    time: int
    energy: int
    z: int = 0
    name: str = "nom"


@dataclass(frozen=True)
class TinyInstance:
    name: str
    nodes: tuple[str, ...]
    depot: str
    chargers: frozenset[str]
    customers: frozenset[str]
    windows: dict[str, tuple[int, int]]  # ready, due for service start
    service: dict[str, int]
    arcs: dict[tuple[str, str], tuple[ArcMode, ...]]
    battery: int
    charge_rate: int  # time per SOC unit
    gamma: int
    start_soc: int
    start_time: int = 0
    max_depth: int = 12


@dataclass(frozen=True)
class State:
    time: int
    node: str
    soc: int
    remaining: frozenset[str]
    gamma_rem: int
    done: bool = False

    def key(self) -> tuple:
        return (self.time, self.node, self.soc, tuple(sorted(self.remaining)), self.gamma_rem, self.done)


@dataclass
class Trace:
    status: str
    actions: list = field(default_factory=list)
    note: str = ""
