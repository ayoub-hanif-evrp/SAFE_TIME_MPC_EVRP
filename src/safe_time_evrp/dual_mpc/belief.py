"""Causal belief / uncertainty-set updates for shared energy parameters.

Updates use only completed traversals with available energy measurements.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dual_mpc.energy_param import ArcFeature


@dataclass(frozen=True)
class DiscreteBelief:
    """Finite-support Bayesian belief over scalar theta values."""

    support: tuple[float, ...]
    probs: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.support) != len(self.probs):
            raise ValueError("support/probs length mismatch")
        if abs(sum(self.probs) - 1.0) > 1e-9:
            raise ValueError("probs must sum to 1")

    @staticmethod
    def uniform(support: tuple[float, ...]) -> DiscreteBelief:
        n = len(support)
        return DiscreteBelief(support, tuple(1.0 / n for _ in support))

    def mean(self) -> float:
        return sum(t * p for t, p in zip(self.support, self.probs, strict=True))

    def update_from_observation(
        self,
        feature: ArcFeature,
        observed_energy: float,
        *,
        load: float = 0.0,
        noise_tol: float = 1e-9,
    ) -> DiscreteBelief:
        """Likelihood: |e - (base + informative*theta + load_coef*load)| <= noise_tol.

        For the exact dual toy, informative arcs have zero noise and fully separate thetas.
        """
        weights: list[float] = []
        for theta, prior in zip(self.support, self.probs, strict=True):
            pred = feature.base + feature.informative * theta + feature.load_coef * load
            like = 1.0 if abs(observed_energy - pred) <= noise_tol + 1e-12 else 0.0
            weights.append(prior * like)
        total = sum(weights)
        if total <= 0:
            # Observation inconsistent with model — keep prior (documented failure mode).
            return self
        probs = tuple(w / total for w in weights)
        return DiscreteBelief(self.support, probs)

    def support_set(self, *, mass_tol: float = 1e-12) -> frozenset[float]:
        return frozenset(t for t, p in zip(self.support, self.probs, strict=True) if p > mass_tol)


@dataclass(frozen=True)
class BoundedErrorSet:
    """Deterministic set-membership for scalar theta under |e - phi^T theta| <= eps_bar."""

    intervals: tuple[tuple[float, float], ...]  # union of closed intervals

    @staticmethod
    def from_bounds(low: float, high: float) -> BoundedErrorSet:
        if high < low:
            raise ValueError("empty initial set")
        return BoundedErrorSet(((low, high),))

    def contains(self, theta: float) -> bool:
        return any(lo - 1e-12 <= theta <= hi + 1e-12 for lo, hi in self.intervals)

    def update(
        self,
        feature: ArcFeature,
        observed_energy: float,
        *,
        load: float = 0.0,
        eps_bar: float = 0.0,
    ) -> BoundedErrorSet:
        """Intersect with thetas consistent with the observation.

        For scalar model e = base + informative*theta + load_coef*load:
        if informative == 0, observation does not constrain theta (unless inconsistency).
        """
        residual_center = observed_energy - feature.base - feature.load_coef * load
        if abs(feature.informative) <= 1e-15:
            # Uninformative arc: accept if residual within eps of 0*theta (=0) wait:
            # e ≈ base + load term; if |observed - base - load| > eps, inconsistent.
            if abs(residual_center) > eps_bar + 1e-12:
                return BoundedErrorSet(())  # empty
            return self
        # |residual_center - informative * theta| <= eps_bar
        # => theta in [(rc - eps)/inf, (rc + eps)/inf] with sign of informative
        lo_raw = (residual_center - eps_bar) / feature.informative
        hi_raw = (residual_center + eps_bar) / feature.informative
        lo_new, hi_new = (min(lo_raw, hi_raw), max(lo_raw, hi_raw))
        out: list[tuple[float, float]] = []
        for lo, hi in self.intervals:
            a, b = max(lo, lo_new), min(hi, hi_new)
            if a <= b + 1e-12:
                out.append((a, b))
        return BoundedErrorSet(tuple(out))

    def is_empty(self) -> bool:
        return len(self.intervals) == 0
