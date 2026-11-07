"""Shared low-dimensional energy parameter model for dual-control experiments.

True consumption on an arc:
    e = phi(arc, load)^T theta_star + noise

Only completed physical traversals yield observations. Anticipated arcs do not.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ArcFeature:
    """Known physical feature vector components (proxy-safe)."""

    arc_id: str
    base: float  # known nominal energy proxy (distance * rate)
    informative: float  # nonzero only on arcs that probe the shared factor
    load_coef: float = 0.0


@dataclass(frozen=True)
class ParametricEnergy:
    """Energy = base + informative * theta + load_coef * load.

    ``theta`` is a scalar shared latent factor (e.g. adverse consumption regime).
    """

    theta: float
    noise_bound: float = 0.0
    name: str = "shared_scalar_theta"

    def travel_energy(self, feature: ArcFeature, *, load: float = 0.0) -> float:
        return float(feature.base + feature.informative * self.theta + feature.load_coef * load)

    def observe(self, feature: ArcFeature, *, load: float = 0.0, noise: float = 0.0) -> float:
        """Plant observation after a completed traversal."""
        return self.travel_energy(feature, load=load) + float(noise)


@dataclass
class SharedThetaWorld:
    """Simulator-side ground truth. Controllers must not read ``theta_star``."""

    theta_star: float
    noise_bound: float = 0.0
    energy: ParametricEnergy | None = None

    def __post_init__(self) -> None:
        if self.energy is None:
            self.energy = ParametricEnergy(theta=self.theta_star, noise_bound=self.noise_bound)

    def realize(self, feature: ArcFeature, *, load: float = 0.0, noise: float = 0.0) -> float:
        assert self.energy is not None
        return self.energy.observe(feature, load=load, noise=noise)
