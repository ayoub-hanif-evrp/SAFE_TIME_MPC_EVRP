"""Replaceable energy models.

The nominal model is the Schneider et al. (2014) linear map stored on each arc:
energy = r * distance, independent of payload. It is not a calibrated kWh model.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.instance import Arc, Instance

EPS = 1e-9


class EnergyModelError(ValueError):
    pass


@dataclass(frozen=True)
class NominalLinearEnergy:
    """Deterministic benchmark energy. Payload does not enter the 2014 formula."""

    name: str = "nominal_linear_schneider"

    def travel_energy(
        self,
        instance: Instance,
        arc: Arc,
        *,
        soc: float,
        load: float,
    ) -> float:
        del soc, load
        if arc.energy < -EPS:
            raise EnergyModelError("arc energy is negative")
        return arc.energy

    def charge_duration(
        self,
        soc: float,
        target: float,
        inverse_rate: float,
    ) -> float:
        if target < soc - EPS:
            raise EnergyModelError("charge target is below the current state of charge")
        if inverse_rate < 0:
            raise EnergyModelError("inverse recharge rate is negative")
        return inverse_rate * max(0.0, target - soc)

    def description(self) -> str:
        return (
            "Nominal deterministic energy equal to the benchmark arc energy "
            "(consumption rate times the source distance). No electrothermal model."
        )


@dataclass(frozen=True)
class ScaledNominalEnergy:
    """Test double. The factor is a design assumption, not a measurement."""

    factor: float
    name: str = "scaled_nominal_design_assumption"

    def __post_init__(self) -> None:
        if self.factor < 0:
            raise EnergyModelError("energy scale cannot be negative")

    def travel_energy(
        self,
        instance: Instance,
        arc: Arc,
        *,
        soc: float,
        load: float,
    ) -> float:
        del instance, soc, load
        return self.factor * arc.energy

    def charge_duration(self, soc: float, target: float, inverse_rate: float) -> float:
        return NominalLinearEnergy().charge_duration(soc, target, inverse_rate)

    def description(self) -> str:
        return (
            f"Nominal arc energy multiplied by {self.factor}. "
            "This factor is a design assumption for tests, not a field calibration."
        )


@dataclass(frozen=True)
class DesignAssumptionEnergyBounds:
    """Interval label only. Part 1 does not route against these bounds."""

    lower_factor: float
    upper_factor: float
    evidence: str = "design_assumption_not_calibrated"

    def __post_init__(self) -> None:
        if not (0 <= self.lower_factor <= self.upper_factor):
            raise EnergyModelError("energy bounds must satisfy 0 <= lower <= upper")

    def as_record(self) -> dict[str, float | str]:
        return {
            "lower_factor": self.lower_factor,
            "upper_factor": self.upper_factor,
            "evidence": self.evidence,
        }
