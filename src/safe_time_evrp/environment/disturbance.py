"""Separately versioned plant disturbance for travel time and energy.

Factors are sampled when an arc is dispatched. The controller never receives the
future realization stream. Schneider instance tables are not modified.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from safe_time_evrp.environment.energy import EPS


class DisturbanceError(ValueError):
    pass


_MODES = {
    "nominal",
    "upper",
    "lower",
    "mixed",
    "adversarial_energy",
    "adversarial_time",
    "out_of_set",
}


@dataclass
class ArcDisturbanceSampler:
    """Deterministic per-arc factor sampler.

    ``out_of_set`` deliberately exceeds the rectangle and is only for stress tests.
    """

    time_lower: float = 1.0
    time_upper: float = 1.0
    energy_lower: float = 1.0
    energy_upper: float = 1.0
    seed: int = 0
    mode: str = "nominal"
    version: str = "disturbance_v1"
    _rng: np.random.Generator = field(init=False, repr=False)
    history: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.mode not in _MODES:
            raise DisturbanceError(f"unknown disturbance mode {self.mode}")
        if self.time_lower < 0 or self.energy_lower < 0:
            raise DisturbanceError("disturbance factors cannot be negative")
        if self.time_lower > self.time_upper or self.energy_lower > self.energy_upper:
            raise DisturbanceError("disturbance lower bound exceeds the upper bound")
        self._rng = np.random.default_rng(self.seed)

    def factors(self, origin: str, destination: str) -> tuple[float, float]:
        if self.mode == "nominal":
            time_f, energy_f = 1.0, 1.0
        elif self.mode == "upper":
            time_f, energy_f = self.time_upper, self.energy_upper
        elif self.mode == "lower":
            time_f, energy_f = self.time_lower, self.energy_lower
        elif self.mode == "adversarial_energy":
            time_f, energy_f = self.time_upper, self.energy_upper
        elif self.mode == "adversarial_time":
            time_f, energy_f = self.time_upper, self.energy_lower
        elif self.mode == "out_of_set":
            time_f = self.time_upper * 1.5
            energy_f = self.energy_upper * 1.5
        else:  # mixed
            time_f = float(self._rng.uniform(self.time_lower, self.time_upper))
            energy_f = float(self._rng.uniform(self.energy_lower, self.energy_upper))
        record = {
            "origin": origin,
            "destination": destination,
            "time_factor": time_f,
            "energy_factor": energy_f,
            "mode": self.mode,
            "seed": self.seed,
            "version": self.version,
            "in_set": (
                self.time_lower - EPS <= time_f <= self.time_upper + EPS
                and self.energy_lower - EPS <= energy_f <= self.energy_upper + EPS
            ),
        }
        self.history.append(record)
        return time_f, energy_f
