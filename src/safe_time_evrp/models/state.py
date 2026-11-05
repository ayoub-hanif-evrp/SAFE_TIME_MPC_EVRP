"""Fleet, request, and plan state used by the simulator and the controller."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RequestStatus(str, Enum):
    HIDDEN = "hidden"
    ANNOUNCED = "announced"
    DEFERRED = "deferred"
    ACCEPTED = "accepted"
    IN_SERVICE = "in_service"
    COMPLETED = "completed"
    REJECTED = "rejected"
    ACCEPTED_UNFULFILLED = "accepted_unfulfilled"


class VehicleStatus(str, Enum):
    IDLE = "idle"
    WAITING = "waiting"
    TRAVELING = "traveling"
    SERVING = "serving"
    CHARGING = "charging"


@dataclass(frozen=True)
class Visit:
    node_id: str
    purpose: str  # service, charge, reload, return
    charge_target: float | None = None

    def __post_init__(self) -> None:
        if self.purpose not in {"service", "charge", "reload", "return"}:
            raise ValueError(f"unknown visit purpose {self.purpose}")


@dataclass(frozen=True)
class Anchor:
    """State at which a not-yet-started suffix may be executed."""

    node: str
    time: float
    soc: float
    load: float
    onboard: frozenset[str]


@dataclass(frozen=True)
class VehicleView:
    id: str
    status: str
    node: str
    soc: float
    load: float
    onboard: tuple[str, ...]
    anchor: Anchor
    locked_destination: str | None


@dataclass(frozen=True)
class Observation:
    """Policy view. Hidden future releases are not fields of this object."""

    time: float
    vehicles: tuple[VehicleView, ...]
    released_open: tuple[str, ...]
    accepted: tuple[str, ...]
    completed: tuple[str, ...]
    rejected: tuple[str, ...]
    in_service: tuple[str, ...]
    deferred: tuple[str, ...]


@dataclass
class LogRecord:
    time: float
    seq: int
    kind: str
    vehicle_id: str | None = None
    data: dict = field(default_factory=dict)


@dataclass
class Decision:
    time: float
    routes: dict[str, list[Visit]]
    accepted: list[str]
    newly_accepted: list[str]
    rejected: list[str]
    deferred: list[str]
    fallback_used: bool
    no_feasible_continuation: bool
    horizon_extended: bool
    planned_service: list[str]
    total_distance: float
    total_charge_time: float
    optimize_seconds: float
    trigger: str
    locked_destinations: dict[str, str | None]
    notes: list[str] = field(default_factory=list)
