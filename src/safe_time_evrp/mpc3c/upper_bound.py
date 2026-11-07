"""Compatibility shim: Gate 3F offline helpers reclassified (Gate 4).

``offline_service_upper_bound`` historically returned a constructive heuristic
service count. That quantity is a **feasible lower bound** on the offline
optimum, not an upper bound. Prefer ``offline_reference.offline_service_reference``.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.instance import Instance
from safe_time_evrp.mpc3c.offline_reference import (
    OfflineReferenceReport,
    a_priori_impossible,
    constructive_feasible_lower_bound,
    is_exploratory_middle_band,
    offline_service_reference,
    window_impossible,
)

__all__ = [
    "UpperBoundReport",
    "a_priori_impossible",
    "window_impossible",
    "offline_service_upper_bound",
    "is_middle_regime",
    "offline_service_reference",
]


@dataclass(frozen=True)
class UpperBoundReport:
    """Deprecated Gate 3F shape. Fields retain names for callers; semantics corrected."""

    n_customers: int
    n_announced: int
    n_a_priori_impossible: int
    static_constructive_served: int
    static_service_rate: float
    a_priori_impossible_ids: tuple[str, ...]
    notes: tuple[str, ...]


def offline_service_upper_bound(
    instance: Instance,
    releases: list[tuple[str, float]],
    *,
    fleet_size: int,
) -> UpperBoundReport:
    """Deprecated name. Returns constructive **feasible lower bound** indicators.

    Does **not** certify an offline service upper bound. Use
    ``offline_service_reference`` for labeled FEASIBLE_LOWER_BOUND /
    CERTIFIED_UPPER_BOUND / EXACT_OPTIMUM / UNKNOWN.
    """
    ref = offline_service_reference(instance, releases, fleet_size=fleet_size, try_exact=False)
    served, _ = constructive_feasible_lower_bound(instance, releases, fleet_size=fleet_size)
    return UpperBoundReport(
        n_customers=ref.n_customers,
        n_announced=ref.n_announced,
        n_a_priori_impossible=ref.n_window_impossible,
        static_constructive_served=served,
        static_service_rate=served / max(ref.n_announced, 1),
        a_priori_impossible_ids=ref.window_impossible_ids,
        notes=ref.notes
        + (
            "DEPRECATED_NAME_offline_service_upper_bound",
            "value_is_FEASIBLE_LOWER_BOUND_not_upper_bound",
        ),
    )


def is_middle_regime(report: UpperBoundReport, *, low: float = 0.40, high: float = 0.80) -> bool:
    """Exploratory band on constructive LB rate — not a certified middle regime."""
    from safe_time_evrp.mpc3c.offline_reference import BoundKind

    fake = OfflineReferenceReport(
        n_customers=report.n_customers,
        n_announced=report.n_announced,
        n_window_impossible=report.n_a_priori_impossible,
        window_impossible_ids=report.a_priori_impossible_ids,
        feasible_lower_bound=report.static_constructive_served,
        certified_upper_bound=None,
        exact_optimum=None,
        bound_kind=BoundKind.HEURISTIC_INDICATOR,
        service_rate_lb=report.static_service_rate,
        service_rate_ub=None,
        notes=report.notes,
    )
    return is_exploratory_middle_band(fake, low=low, high=high)
