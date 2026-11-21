"""adaptive_compute_v1 — unified scenario/ALNS expansion under a hard wall budget."""

from __future__ import annotations

from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Observation


def remaining_dynamic_mass_frac(observation: Observation, instance: Instance) -> float:
    """Proxy for degree of dynamism still ahead (public info only)."""
    pub = getattr(observation, "public_customer_count", None)
    total = int(pub) if pub is not None else len(instance.customer_ids())
    if total <= 0:
        return 0.0
    announced = (
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.completed)
        | set(observation.rejected)
        | set(observation.in_service)
        | set(observation.deferred)
    )
    remaining = max(0, total - len(announced))
    return remaining / float(total)


def min_soc_frac(observation: Observation, instance: Instance) -> float:
    cap = float(instance.vehicle_type.battery_capacity)
    if cap <= 1e-12 or not observation.vehicles:
        return 1.0
    return min(float(v.soc) / cap for v in observation.vehicles)


def time_slack_frac(observation: Observation, horizon: float) -> float:
    h = max(float(horizon), 1e-9)
    return max(0.0, (h - float(observation.time)) / h)


def adaptive_compute_v1(
    observation: Observation,
    instance: Instance,
    *,
    horizon: float,
    n_scenarios_base: int = 2,
    n_scenarios_max: int = 4,
    alns_base: int = 10,
    alns_max: int = 20,
    remaining_budget_frac: float | None = None,
) -> dict:
    """Expand scenarios/ALNS when slack is tight or remaining dynamic mass is high.

    Never exceeds max; if little wall budget remains, shrink toward base/1.
    """
    mass = remaining_dynamic_mass_frac(observation, instance)
    soc = min_soc_frac(observation, instance)
    tslack = time_slack_frac(observation, horizon)
    stress = mass >= 0.35 or soc <= 0.35 or tslack <= 0.40
    n_sc = int(n_scenarios_max if stress else n_scenarios_base)
    alns = int(alns_max if stress else alns_base)
    # Late in the decide wall: prefer fewer scenarios so commit still happens.
    if remaining_budget_frac is not None and remaining_budget_frac < 0.25:
        n_sc = min(n_sc, max(1, n_scenarios_base))
        alns = min(alns, alns_base)
    return {
        "policy": "adaptive_compute_v1",
        "stress": stress,
        "remaining_dynamic_mass_frac": mass,
        "min_soc_frac": soc,
        "time_slack_frac": tslack,
        "n_scenarios": max(1, n_sc),
        "alns_iterations": max(1, alns),
    }
