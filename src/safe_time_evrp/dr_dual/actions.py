"""Explicit physical control set for the tiny dual-EVRP model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ActionKind(str, Enum):
    TRAVEL = "travel"
    SERVE = "serve"
    CHARGE_FULL = "charge_full"
    WAIT = "wait"
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    NOOP = "noop"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    vehicle_id: str
    segment_id: str | None = None
    customer_id: str | None = None
    charger_id: str | None = None
    wait_duration: float = 0.0

    def key(self) -> str:
        return (
            f"{self.kind.value}|{self.vehicle_id}|{self.segment_id}|"
            f"{self.customer_id}|{self.charger_id}|{self.wait_duration}"
        )
