"""Dynamic release mechanisms for a fixed customer pool.

Repeated seeds on one parent instance are repeated scenarios, not independent
geometries. Independent comparisons use different parent instances.

None of these mechanisms conditions a release time on an offline route.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from safe_time_evrp.models.instance import Instance


@dataclass(frozen=True)
class DynamicScenario:
    """Ground-truth release list. Pass only the observation into a policy."""

    parent_instance: str
    mechanism: str
    seed: int
    releases: tuple[tuple[str, float], ...]
    version: str = "dynamic-release-v1"

    def releases_visible_at(self, time: float) -> tuple[str, ...]:
        return tuple(cid for cid, release in self.releases if release <= time)

    def hidden_at(self, time: float) -> tuple[str, ...]:
        return tuple(cid for cid, release in self.releases if release > time)


def indexed_stagger(
    instance: Instance,
    *,
    step: float,
    customer_ids: list[str] | None = None,
    seed: int = 0,
) -> DynamicScenario:
    """Release the sorted pool at 0, step, 2 step, ... Seed does not move times.

    The seed is recorded so a caller can see that this mechanism is deterministic
    given the parent geometry and the step. It is not used to hide a route.
    """
    del seed
    chosen = customer_ids or instance.customer_ids()
    releases = tuple((cid, index * step) for index, cid in enumerate(sorted(chosen)))
    return DynamicScenario(instance.name, "indexed_stagger", 0, releases)


def uniform_releases(
    instance: Instance,
    *,
    seed: int,
    release_horizon: float,
    customer_ids: list[str] | None = None,
) -> DynamicScenario:
    """Independent Uniform(0, release_horizon) release for each selected customer."""
    if release_horizon <= 0:
        raise ValueError("release horizon must be positive")
    chosen = sorted(customer_ids or instance.customer_ids())
    rng = np.random.default_rng(seed)
    draws = rng.uniform(0.0, release_horizon, size=len(chosen))
    releases = tuple((cid, float(draw)) for cid, draw in zip(chosen, draws, strict=True))
    return DynamicScenario(instance.name, "uniform", seed, releases)


def lead_time_releases(
    instance: Instance,
    *,
    seed: int,
    lead_min: float,
    lead_max: float,
    customer_ids: list[str] | None = None,
) -> DynamicScenario:
    """Announce each customer a random lead before its ready time, clipped at 0.

    The lead is not chosen to make the customer feasible.
    """
    if lead_min < 0 or lead_max < lead_min:
        raise ValueError("invalid lead-time interval")
    chosen = sorted(customer_ids or instance.customer_ids())
    rng = np.random.default_rng(seed)
    leads = rng.uniform(lead_min, lead_max, size=len(chosen))
    releases = []
    for cid, lead in zip(chosen, leads, strict=True):
        ready = instance.node(cid).window.ready
        releases.append((cid, max(0.0, ready - float(lead))))
    return DynamicScenario(instance.name, "lead_time", seed, tuple(releases))


def poisson_pool_releases(
    instance: Instance,
    *,
    seed: int,
    horizon: float,
    rates: list[tuple[float, float, float]],
    customer_ids: list[str] | None = None,
) -> DynamicScenario:
    """Assign non-homogeneous Poisson epochs to a random permutation of the pool.

    ``rates`` is a list of ``(start, end, lambda)`` pieces. Epochs are generated
    by thinning against the maximum rate. If more epochs than customers are drawn,
    the extra epochs are discarded. If fewer epochs are drawn, the remaining
    customers are not released. This is a finite-pool sampling interpretation,
    not an infinite-request Poisson process and not a feasibility filter.
    """
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    pieces = [(start, end, rate) for start, end, rate in rates if end > start and rate >= 0]
    if not pieces:
        raise ValueError("poisson pieces are empty")
    lam_max = max(rate for _, _, rate in pieces)
    chosen = sorted(customer_ids or instance.customer_ids())
    rng = np.random.default_rng(seed)
    epochs: list[float] = []
    if lam_max > 0:
        clock = 0.0
        while clock < horizon:
            clock += float(rng.exponential(1.0 / lam_max))
            if clock >= horizon:
                break
            rate = 0.0
            for start, end, piece_rate in pieces:
                if start <= clock < end:
                    rate = piece_rate
                    break
            if rng.random() <= rate / lam_max:
                epochs.append(clock)
    order = list(chosen)
    rng.shuffle(order)
    paired = list(zip(order, epochs, strict=False))
    releases = tuple(sorted(paired, key=lambda item: (item[1], item[0])))
    return DynamicScenario(instance.name, "poisson_pool", seed, releases)


def independent_parent_scenarios(
    instances: list[Instance],
    *,
    seed: int,
    release_horizon: float,
) -> list[DynamicScenario]:
    """One uniform scenario per parent geometry. Seeds differ by parent index."""
    return [
        uniform_releases(instance, seed=seed + index, release_horizon=release_horizon)
        for index, instance in enumerate(instances)
    ]
