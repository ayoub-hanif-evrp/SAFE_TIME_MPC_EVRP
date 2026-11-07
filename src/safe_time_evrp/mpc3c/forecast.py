"""Request-arrival forecasts for Gate 3D predictive horizons.

Forecasts use only information available at decision time: an empirical arrival
model fitted on a train split, or an explicit scenario set. Hidden customers from
the live episode are never read through ``instance.customer_ids()`` remaining sets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean

from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Observation, Visit


@dataclass(frozen=True)
class ForecastCustomer:
    customer_id: str
    ready_time: float
    due_time: float
    source: str = "scenario"


@dataclass
class ArrivalForecast:
    """Scenario set of future arrivals known to the controller as forecasts only."""

    scenarios: list[list[ForecastCustomer]] = field(default_factory=list)
    train_interarrival_mean: float | None = None
    train_customer_pool: tuple[str, ...] = ()

    def sample_within(
        self,
        now: float,
        horizon: float,
        *,
        scenario_index: int = 0,
        exclude: set[str] | None = None,
    ) -> list[ForecastCustomer]:
        ban = exclude or set()
        if not self.scenarios:
            return []
        idx = scenario_index % len(self.scenarios)
        out: list[ForecastCustomer] = []
        for item in self.scenarios[idx]:
            if item.customer_id in ban:
                continue
            if now - 1e-12 <= item.ready_time <= now + horizon + 1e-12:
                out.append(item)
        return out


def fit_empirical_arrivals(
    instances: list[Instance],
) -> ArrivalForecast:
    """Fit a simple inter-arrival model on train-split ready times."""
    ready_times: list[float] = []
    pool: list[str] = []
    for inst in instances:
        for cid in inst.customer_ids():
            ready_times.append(float(inst.node(cid).window.ready))
            pool.append(cid)
    if not ready_times:
        return ArrivalForecast()
    ready_times = sorted(ready_times)
    gaps = [ready_times[i + 1] - ready_times[i] for i in range(len(ready_times) - 1)]
    mu = mean(gaps) if gaps else mean(ready_times)
    return ArrivalForecast(
        scenarios=[],
        train_interarrival_mean=mu,
        train_customer_pool=tuple(sorted(set(pool))),
    )


def build_scenarios_for(
    instance: Instance,
    model: ArrivalForecast,
    *,
    n_scenarios: int = 3,
    seed: int = 0,
    rate_scale: float = 1.0,
) -> ArrivalForecast:
    """Materialize scenario arrivals on ``instance`` using train inter-arrival stats."""
    customers = list(instance.customer_ids())
    if not customers:
        return ArrivalForecast(scenarios=[], train_interarrival_mean=model.train_interarrival_mean)
    mu = model.train_interarrival_mean
    if mu is None or mu <= 0:
        base = [
            ForecastCustomer(
                cid,
                float(instance.node(cid).window.ready),
                float(instance.node(cid).window.due),
                source="instance_ready",
            )
            for cid in customers
        ]
        return ArrivalForecast(
            scenarios=[list(base) for _ in range(n_scenarios)],
            train_interarrival_mean=mu,
            train_customer_pool=model.train_customer_pool,
        )

    scenarios: list[list[ForecastCustomer]] = []
    state = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    for s in range(n_scenarios):
        items: list[ForecastCustomer] = []
        t = 0.0
        order = list(customers)
        for i in range(len(order) - 1, 0, -1):
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            j = state % (i + 1)
            order[i], order[j] = order[j], order[i]
        for cid in order:
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            u = (state % 10_000) / 10_000.0
            u = min(max(u, 1e-6), 1 - 1e-6)
            gap = (mu / rate_scale) * (0.05 + 1.9 * u)
            t += gap
            due = float(instance.node(cid).window.due)
            ready = min(t, due)
            items.append(ForecastCustomer(cid, ready, due, source=f"scenario_{s}"))
        scenarios.append(items)
    return ArrivalForecast(
        scenarios=scenarios,
        train_interarrival_mean=mu,
        train_customer_pool=model.train_customer_pool,
    )


def synthetic_poisson_releases(
    instance: Instance,
    *,
    seed: int = 0,
    mean_interarrival: float | None = None,
) -> list[tuple[str, float]]:
    """Generate an actual plant release stream (not visible as forecasts)."""
    customers = list(instance.customer_ids())
    if not customers:
        return []
    dues = [float(instance.node(c).window.due) for c in customers]
    horizon = max(dues) if dues else 10.0
    mu = mean_interarrival if mean_interarrival is not None else max(horizon / max(len(customers), 1), 0.1)
    state = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    order = list(customers)
    for i in range(len(order) - 1, 0, -1):
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        j = state % (i + 1)
        order[i], order[j] = order[j], order[i]
    releases: list[tuple[str, float]] = []
    t = 0.0
    for cid in order:
        state = (state * 1103515245 + 12345) & 0x7FFFFFFF
        u = (state % 10_000) / 10_000.0
        u = min(max(u, 1e-6), 1 - 1e-6)
        t += mu * (0.05 + 1.9 * u)
        ready_cap = float(instance.node(cid).window.due)
        releases.append((cid, min(t, ready_cap)))
    return releases


def visible_forecast(
    observation: Observation,
    forecast: ArrivalForecast | None,
    horizon: float,
    *,
    scenario_index: int = 0,
) -> list[ForecastCustomer]:
    """Forecast customers inside the planning horizon, excluding already-known IDs."""
    if forecast is None:
        return []
    known = (
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.completed)
        | set(observation.rejected)
        | set(observation.in_service)
        | set(observation.deferred)
    )
    return forecast.sample_within(
        observation.time,
        horizon,
        scenario_index=scenario_index,
        exclude=known,
    )


def information_safe_remaining(
    observation: Observation,
    forecast_customers: list[ForecastCustomer],
    routes: dict[str, list[Visit]] | None = None,
) -> list[str]:
    """Remaining set for flexibility scoring: released/accepted + forecasts only."""
    served: set[str] = set(observation.completed) | set(observation.in_service)
    if routes:
        for visits in routes.values():
            for visit in visits:
                if visit.purpose == "service":
                    served.add(visit.node_id)
    remaining: list[str] = []
    for cid in observation.released_open:
        if cid not in served and cid not in observation.rejected:
            remaining.append(cid)
    for item in forecast_customers:
        if item.customer_id not in served and item.customer_id not in remaining:
            remaining.append(item.customer_id)
    return remaining
