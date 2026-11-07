"""Shared upper-bound status API (no silent discard of feasible actions)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BoundStatus(str, Enum):
    VALID_BOUND = "VALID_BOUND"
    UNSUPPORTED_BOUND = "UNSUPPORTED_BOUND"
    PROVEN_INFEASIBLE = "PROVEN_INFEASIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class BoundResult:
    status: BoundStatus
    value: float | None = None
    notes: tuple[str, ...] = ()

    @staticmethod
    def valid(value: float, *notes: str) -> BoundResult:
        return BoundResult(BoundStatus.VALID_BOUND, value, notes)

    @staticmethod
    def unsupported(*notes: str) -> BoundResult:
        return BoundResult(BoundStatus.UNSUPPORTED_BOUND, None, notes)

    @staticmethod
    def infeasible(*notes: str) -> BoundResult:
        return BoundResult(BoundStatus.PROVEN_INFEASIBLE, None, notes)

    @staticmethod
    def unknown(*notes: str) -> BoundResult:
        return BoundResult(BoundStatus.UNKNOWN, None, notes)
