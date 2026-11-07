"""Physical + information state for decision-relevant dual MPC."""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.dual_mpc.belief import DiscreteBelief


@dataclass(frozen=True)
class VehicleState:
    vehicle_id: str
    node: str
    time: float
    soc: float
    load: float = 0.0
    busy_until: float = 0.0  # noninterruptible action end


@dataclass(frozen=True)
class WorldState:
    """Controller-visible state (never includes theta_star)."""

    vehicles: tuple[VehicleState, ...]
    accepted: frozenset[str]
    completed: frozenset[str]
    rejected: frozenset[str]
    announced: frozenset[str]
    belief: DiscreteBelief
    stage: int = 0

    def vehicle(self, vid: str) -> VehicleState:
        for v in self.vehicles:
            if v.vehicle_id == vid:
                return v
        raise KeyError(vid)


@dataclass
class PlantLog:
    """Independent replay log of physical transitions and observations."""

    events: list[dict] = field(default_factory=list)

    def record(self, **kwargs) -> None:
        self.events.append(dict(kwargs))
