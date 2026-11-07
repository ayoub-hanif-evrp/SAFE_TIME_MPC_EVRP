"""Explicit announcement-process specifications (Gate 4).

Service-window openings on static benchmarks are **not** order-arrival
observations. Do not estimate Poisson rates by pooling ``window.ready`` times
across independent training instances.

Use either:
- verified operational request-arrival records, or
- a synthetic homogeneous Poisson process with **preregistered** parameters
  chosen independently of evaluation outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from safe_time_evrp.models.instance import Instance
from safe_time_evrp.mpc3c.forecast import synthetic_poisson_releases
from safe_time_evrp.mpc3c.seeds import stable_seed


class AnnouncementSource(str, Enum):
    PREREGISTERED_POISSON = "preregistered_homogeneous_poisson"
    WINDOW_READY_AS_ANNOUNCE = "window_ready_as_announce_exploratory_only"
    OPERATIONAL_LOG = "operational_request_log"


@dataclass(frozen=True)
class AnnouncementProcessSpec:
    """Preregistered announcement process — parameters fixed before looking at scores."""

    source: AnnouncementSource
    mean_interarrival: float | None = None
    spec_id: str = ""
    notes: tuple[str, ...] = ()

    def materialize(
        self,
        instance: Instance,
        *,
        seed_key: str,
    ) -> list[tuple[str, float]]:
        if self.source is AnnouncementSource.PREREGISTERED_POISSON:
            if self.mean_interarrival is None or self.mean_interarrival <= 0:
                raise ValueError("preregistered Poisson requires mean_interarrival > 0")
            seed = stable_seed("announce", seed_key, self.spec_id)
            return synthetic_poisson_releases(
                instance,
                seed=seed,
                mean_interarrival=float(self.mean_interarrival),
            )
        if self.source is AnnouncementSource.WINDOW_READY_AS_ANNOUNCE:
            return [(cid, float(instance.node(cid).window.ready)) for cid in instance.customer_ids()]
        raise NotImplementedError(f"announcement source {self.source} requires verified operational logs")


# Preregistered development specs (chosen for Gate 4; not fitted to maximize RH gap).
GATE4_DEV_ANNOUNCEMENT_SPECS: tuple[AnnouncementProcessSpec, ...] = (
    AnnouncementProcessSpec(
        source=AnnouncementSource.PREREGISTERED_POISSON,
        mean_interarrival=8.0,
        spec_id="gate4_dev_mu8",
        notes=("synthetic_poisson", "mu=8.0", "preregistered_before_controller_scores"),
    ),
    AnnouncementProcessSpec(
        source=AnnouncementSource.PREREGISTERED_POISSON,
        mean_interarrival=15.0,
        spec_id="gate4_dev_mu15",
        notes=("synthetic_poisson", "mu=15.0", "preregistered_before_controller_scores"),
    ),
    AnnouncementProcessSpec(
        source=AnnouncementSource.PREREGISTERED_POISSON,
        mean_interarrival=25.0,
        spec_id="gate4_dev_mu25",
        notes=("synthetic_poisson", "mu=25.0", "preregistered_before_controller_scores"),
    ),
)


def pooled_ready_gaps_are_not_interarrivals(instances: list[Instance]) -> dict:
    """Document why Gate 3F ``fit_empirical_arrivals`` mu is scientifically invalid as λ̂."""
    ready_times: list[float] = []
    for inst in instances:
        for cid in inst.customer_ids():
            ready_times.append(float(inst.node(cid).window.ready))
    ready_times = sorted(ready_times)
    gaps = [ready_times[i + 1] - ready_times[i] for i in range(len(ready_times) - 1)]
    return {
        "n_instances": len(instances),
        "n_ready_times_pooled": len(ready_times),
        "n_gaps": len(gaps),
        "claim": (
            "Pooled window.ready gaps across independent instances are not "
            "observations of a request announcement process."
        ),
        "gate4_policy": "Do not use these gaps as Poisson mean_interarrival.",
    }
