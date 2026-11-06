"""Rectangular travel-time and energy uncertainty.

These bounds are modeling assumptions. They are not confidence intervals, and they
are not fitted to a hidden evaluation trajectory.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from safe_time_evrp.models.instance import Arc, Instance

_EVIDENCE = {
    "nominal",
    "design_assumption",
    "scenario_derived",
}


class UncertaintyError(ValueError):
    pass


@dataclass(frozen=True)
class RectangularUncertainty:
    """Independent bounds on every arc, as factors of the nominal arc tables.

    A realization may use any travel-time factor in ``[time_lower, time_upper]`` and
    any energy factor in ``[energy_lower, energy_upper]`` on each arc, independently.
    """

    time_lower: float = 1.0
    time_upper: float = 1.0
    energy_lower: float = 1.0
    energy_upper: float = 1.0
    soc_floor: float = 0.0
    evidence: str = "design_assumption"
    monotone_linear: bool = True

    def __post_init__(self) -> None:
        if self.evidence not in _EVIDENCE:
            raise UncertaintyError(
                "uncertainty evidence must be nominal, design_assumption, or scenario_derived. "
                "A held-out physical realization is not an uncertainty set."
            )
        if self.time_lower < 0 or self.energy_lower < 0:
            raise UncertaintyError("uncertainty factors cannot be negative")
        if self.time_lower > self.time_upper or self.energy_lower > self.energy_upper:
            raise UncertaintyError("uncertainty lower bound exceeds the upper bound")
        if self.soc_floor < 0:
            raise UncertaintyError("state-of-charge floor cannot be negative")

    @property
    def assumptions(self) -> tuple[str, ...]:
        return (
            "Rectangular independent bounds on arc travel time and arc energy.",
            f"Travel-time factor in [{self.time_lower}, {self.time_upper}].",
            f"Energy factor in [{self.energy_lower}, {self.energy_upper}].",
            f"State-of-charge floor {self.soc_floor}.",
            f"Evidence class: {self.evidence}.",
            "Bounds are modeling assumptions, not statistical confidence intervals.",
            "The upper corner is the worst case only while travel and charging are monotone.",
        )


def scale_instance(
    instance: Instance,
    *,
    time_factor: float,
    energy_factor: float,
) -> Instance:
    """Independent checker input. Scales the arc tables and leaves the nodes unchanged."""
    arcs: dict[tuple[str, str], Arc] = {}
    for key, arc in instance.arcs.items():
        arcs[key] = replace(
            arc,
            travel_time=arc.travel_time * time_factor,
            energy=arc.energy * energy_factor,
        )
    return replace(instance, arcs=arcs)
