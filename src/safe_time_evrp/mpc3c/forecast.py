"""Information-safe demand forecasts for Gate 3E/3F.

Forecasts are anonymous synthetic customers sampled from **train-only** spatial
and timing distributions. They never inherit evaluation-instance customer IDs,
coordinates, or windows from hidden future requests.

Gate 3F: plant announcements use a true homogeneous Poisson process (exponential
interarrivals). Announcement time is separated from window.ready / window.due.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import mean

from safe_time_evrp.models.instance import (
    Arc,
    Instance,
    Node,
    NodeKind,
    TimeWindow,
    euclidean,
)
from safe_time_evrp.models.state import Observation, Visit
from safe_time_evrp.mpc3c.seeds import stable_seed


@dataclass(frozen=True)
class ForecastCustomer:
    """Anonymous forecast demand unit (not an evaluation customer id)."""

    customer_id: str
    ready_time: float
    due_time: float
    x: float
    y: float
    demand: float = 1.0
    service_time: float = 1.0
    source: str = "anonymous_scenario"


@dataclass(frozen=True)
class TrainDemandAtom:
    x: float
    y: float
    demand: float
    service_time: float
    ready: float
    due: float


@dataclass
class ArrivalForecast:
    """Train-fitted demand model + materialized anonymous scenario samples."""

    scenarios: list[list[ForecastCustomer]] = field(default_factory=list)
    train_atoms: tuple[TrainDemandAtom, ...] = ()
    train_interarrival_mean: float | None = None
    model_id: str = ""

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


def fit_empirical_arrivals(instances: list[Instance]) -> ArrivalForecast:
    """Fit spatial/timing atoms on train-split instances only."""
    atoms: list[TrainDemandAtom] = []
    ready_times: list[float] = []
    for inst in instances:
        for cid in inst.customer_ids():
            node = inst.node(cid)
            atoms.append(
                TrainDemandAtom(
                    float(node.x),
                    float(node.y),
                    float(node.demand),
                    float(node.service_time),
                    float(node.window.ready),
                    float(node.window.due),
                )
            )
            ready_times.append(float(node.window.ready))
    if not atoms:
        return ArrivalForecast(model_id="empty")
    ready_times = sorted(ready_times)
    gaps = [ready_times[i + 1] - ready_times[i] for i in range(len(ready_times) - 1)]
    mu = mean(gaps) if gaps else mean(ready_times)
    return ArrivalForecast(
        scenarios=[],
        train_atoms=tuple(atoms),
        train_interarrival_mean=mu,
        model_id=f"train_atoms={len(atoms)};mu={mu:.6f}",
    )


def _lcg(state: int) -> tuple[int, float]:
    state = (state * 1103515245 + 12345) & 0x7FFFFFFF
    return state, (state % 10_000) / 10_000.0


def build_anonymous_scenarios(
    model: ArrivalForecast,
    *,
    n_scenarios: int = 3,
    customers_per_scenario: int = 3,
    seed: int = 0,
    rate_scale: float = 1.0,
    day_horizon: float = 200.0,
) -> ArrivalForecast:
    """Sample anonymous forecast customers from train atoms (no eval IDs)."""
    if not model.train_atoms:
        return ArrivalForecast(
            scenarios=[[] for _ in range(n_scenarios)],
            train_atoms=model.train_atoms,
            train_interarrival_mean=model.train_interarrival_mean,
            model_id=model.model_id,
        )
    mu = model.train_interarrival_mean or 1.0
    scenarios: list[list[ForecastCustomer]] = []
    state = seed & 0x7FFFFFFF
    for s in range(n_scenarios):
        items: list[ForecastCustomer] = []
        t = 0.0
        for k in range(customers_per_scenario):
            state, u_gap = _lcg(state)
            state, u_pick = _lcg(state)
            atom = model.train_atoms[int(u_pick * len(model.train_atoms)) % len(model.train_atoms)]
            # Jitter location slightly so samples are not exact train clones of eval geometry.
            state, jx = _lcg(state)
            state, jy = _lcg(state)
            x = atom.x + (jx - 0.5) * 0.5
            y = atom.y + (jy - 0.5) * 0.5
            gap = _exponential_gap(mu / rate_scale, u_gap)
            t += gap
            ready = min(t, day_horizon)
            span = max(atom.due - atom.ready, 1.0)
            due = min(day_horizon, ready + span)
            items.append(
                ForecastCustomer(
                    customer_id=f"syn_s{s}_{k}",
                    ready_time=ready,
                    due_time=due,
                    x=x,
                    y=y,
                    demand=max(atom.demand, 0.01),
                    service_time=max(atom.service_time, 0.0),
                    source=f"anonymous_scenario_{s}",
                )
            )
        scenarios.append(items)
    return ArrivalForecast(
        scenarios=scenarios,
        train_atoms=model.train_atoms,
        train_interarrival_mean=model.train_interarrival_mean,
        model_id=model.model_id,
    )


def _exponential_gap(mu: float, u: float) -> float:
    """Homogeneous Poisson interarrival: Exp(mean=mu) via inverse CDF."""
    u = min(max(u, 1e-12), 1.0 - 1e-12)
    return -float(mu) * math.log(1.0 - u)


def build_scenarios_for(
    instance: Instance | None = None,
    model: ArrivalForecast | None = None,
    *,
    n_scenarios: int = 3,
    seed: int = 0,
    rate_scale: float = 1.0,
    day_horizon: float | None = None,
) -> ArrivalForecast:
    """Quarantined compatibility wrapper (Gate 3F).

    Online use with a live evaluation ``instance`` is forbidden because reading
    eval customer dues leaked horizon information. Pass ``day_horizon`` explicitly
    (from train stats or a fixed policy constant) instead.
    """
    if model is None:
        raise ValueError("model is required")
    if instance is not None:
        raise RuntimeError(
            "build_scenarios_for(instance=...) is quarantined (Gate 3F information boundary). "
            "Use build_anonymous_scenarios(model, day_horizon=...) with a horizon that does not "
            "depend on unreleased evaluation customers."
        )
    day = 200.0 if day_horizon is None else float(day_horizon)
    return build_anonymous_scenarios(
        model,
        n_scenarios=n_scenarios,
        customers_per_scenario=min(3, max(1, len(model.train_atoms) // 10 or 1)),
        seed=seed,
        rate_scale=rate_scale,
        day_horizon=day,
    )


def augment_instance_for_planning(instance: Instance, forecasts: list[ForecastCustomer]) -> Instance:
    """Clone geometry and attach anonymous forecast customers as planning-only nodes."""
    if not forecasts:
        return instance
    nodes = dict(instance.nodes)
    arcs = dict(instance.arcs)
    velocity = instance.vehicle_type.velocity or 1.0
    rate = instance.vehicle_type.consumption_rate
    for fc in forecasts:
        if fc.customer_id in nodes:
            continue
        nodes[fc.customer_id] = Node(
            fc.customer_id,
            NodeKind.CUSTOMER,
            fc.x,
            fc.y,
            fc.demand,
            TimeWindow(fc.ready_time, fc.due_time),
            fc.service_time,
        )
    # Complete arcs involving new nodes via Euclidean travel (planning proxy).
    ids = list(nodes)
    for a in ids:
        for b in ids:
            if a == b or (a, b) in arcs:
                continue
            na, nb = nodes[a], nodes[b]
            dist = euclidean(na.x, na.y, nb.x, nb.y)
            travel = dist / velocity if velocity > 0 else dist
            arcs[(a, b)] = Arc(
                origin=a,
                destination=b,
                distance=dist,
                travel_time=travel,
                energy=rate * dist,
                distance_definition="forecast_euclidean_proxy",
                distance_km=dist,
                travel_time_h=travel,
            )
    return Instance(
        name=instance.name + "+forecast",
        nodes=nodes,
        arcs=arcs,
        vehicle_type=instance.vehicle_type,
        depot_id=instance.depot_id,
        source_format=instance.source_format,
        source_name=instance.source_name,
        assumptions=instance.assumptions + ("planning_augmented_anonymous_forecasts",),
        station_capacity=instance.station_capacity,
        metadata=dict(instance.metadata),
    )


def synthetic_poisson_releases(
    instance: Instance,
    *,
    seed: int = 0,
    mean_interarrival: float | None = None,
) -> list[tuple[str, float]]:
    """Homogeneous Poisson announcement times for evaluation customers.

    Announcement time is **not** clamped to window.ready or window.due.
    Service windows remain separate plant constraints. Customers announced after
    their due may be a-priori unserviceable and must be counted in the denominator.
    """
    customers = list(instance.customer_ids())
    if not customers:
        return []
    dues = [float(instance.node(c).window.due) for c in customers]
    horizon = max(dues) if dues else 10.0
    mu = mean_interarrival if mean_interarrival is not None else max(horizon / max(len(customers), 1), 0.1)
    state = seed & 0x7FFFFFFF
    order = list(customers)
    for i in range(len(order) - 1, 0, -1):
        state, u = _lcg(state)
        j = int(u * (i + 1)) % (i + 1)
        order[i], order[j] = order[j], order[i]
    releases: list[tuple[str, float]] = []
    t = 0.0
    for cid in order:
        state, u = _lcg(state)
        t += _exponential_gap(mu, u)
        releases.append((cid, float(t)))
    return releases


def visible_forecast(
    observation: Observation,
    forecast: ArrivalForecast | None,
    horizon: float,
    *,
    scenario_index: int = 0,
) -> list[ForecastCustomer]:
    """Forecast customers inside H; exclude IDs already in the observation."""
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
    """Remaining set for flexibility scoring: released + anonymous forecasts only."""
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


def release_seed_for(instance_name: str) -> int:
    return stable_seed("release", instance_name)


def forecast_seed_for(instance_name: str) -> int:
    return stable_seed("forecast", instance_name)
