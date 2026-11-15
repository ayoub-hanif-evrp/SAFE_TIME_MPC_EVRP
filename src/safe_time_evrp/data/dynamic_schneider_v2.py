"""Schneider-derived dynamic EVRPTW protocol v2 (announcement + fleet corrections).

Protocol v1 results remain frozen under ``docs/experiments/SCHNEIDER_DYNAMIC_RESULTS.json``.
v2 does **not** clamp announcement times into feasibility; late requests are classified.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase
from safe_time_evrp.data.dynamic_schneider import (
    BENCHMARK_LABEL,
    DYNAMICITY_SPECS,
    DynamicEpisode,
    Dynamicity,
    _exponential_gap,
    _family,
    _lcg,
    environment_seed_for,
    latest_feasible_announce_time,
    load_instance,
    policy_seed_for,
)
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.mpc3c.seeds import instance_content_hash

PROTOCOL_VERSION_V2 = "2026-11-14.v2"
FLEET_HARD_CAP_V2 = 20  # explicit; never silently pretend 6 covers 100-customer load


@dataclass(frozen=True)
class ReleaseClassification:
    customer_id: str
    release_time: float
    latest_depot_admit: float
    late_for_depot_admit: bool
    known_at_start: bool


def select_fleet_size_v2(instance: Instance) -> tuple[int, str, dict]:
    """Fleet from load and customer count; cap only at an explicit documented hard limit."""
    customers = instance.customer_ids()
    n = len(customers)
    demand = sum(float(instance.node(cid).demand) for cid in customers)
    cap = float(instance.vehicle_type.load_capacity)
    by_load = max(1, int(math.ceil(demand / cap))) if cap > 0 else 1
    by_count = max(1, int(math.ceil(n / 5.0)))
    uncapped = max(by_load, by_count)
    capped = uncapped > FLEET_HARD_CAP_V2
    fleet = min(FLEET_HARD_CAP_V2, uncapped)
    rule = (
        f"min({FLEET_HARD_CAP_V2}, max(ceil(demand/C)={by_load}, ceil(n/5)={by_count}))"
        f"|uncapped={uncapped}|capped={int(capped)}"
    )
    meta = {
        "by_load": by_load,
        "by_count": by_count,
        "uncapped": uncapped,
        "fleet": fleet,
        "hard_cap": FLEET_HARD_CAP_V2,
        "hit_hard_cap": capped,
        "note": (
            "If hit_hard_cap, the configuration is computationally constrained relative to "
            "the load/customer target; report as such — do not substitute easier fleets."
        ),
    }
    return fleet, rule, meta


def generate_releases_v2(
    instance: Instance,
    *,
    environment_seed: int,
    dynamicity: Dynamicity | str,
) -> tuple[list[tuple[str, float]], tuple[str, ...], tuple[str, ...], str, list[ReleaseClassification]]:
    """Natural Poisson announcements; classify lateness without changing release times."""
    dyn = Dynamicity(dynamicity)
    spec = DYNAMICITY_SPECS[dyn.value]
    customers = list(instance.customer_ids())
    dues = [float(instance.node(c).window.due) for c in customers]
    depot_due = float(instance.node(instance.depot_id).window.due)
    horizon = max([depot_due, *dues]) if customers else depot_due
    mu = max(spec["mean_interarrival_scale"] * horizon / max(len(customers), 1), 0.05)

    state = environment_seed & 0x7FFFFFFF
    order = list(customers)
    for i in range(len(order) - 1, 0, -1):
        state, u = _lcg(state)
        j = int(u * (i + 1)) % (i + 1)
        order[i], order[j] = order[j], order[i]

    n_known = int(math.floor(spec["known_fraction"] * len(order)))
    n_known = min(max(n_known, 0), len(order))
    if dyn is Dynamicity.HIGH and len(order) >= 2:
        n_known = min(n_known, len(order) - 1)
    known = tuple(order[:n_known])
    dynamic = tuple(order[n_known:])

    releases: dict[str, float] = {cid: 0.0 for cid in known}
    t = 0.0
    for cid in dynamic:
        state, u = _lcg(state)
        t += _exponential_gap(mu, u)
        releases[cid] = float(t)  # no feasibility clamp

    classifications: list[ReleaseClassification] = []
    for cid, rt in releases.items():
        latest = latest_feasible_announce_time(instance, cid)
        classifications.append(
            ReleaseClassification(
                customer_id=cid,
                release_time=float(rt),
                latest_depot_admit=float(latest),
                late_for_depot_admit=bool(rt > latest + 1e-12),
                known_at_start=cid in known,
            )
        )
    ordered = sorted(releases.items(), key=lambda kv: (kv[1], kv[0]))
    rule = (
        f"{BENCHMARK_LABEL}|protocol={PROTOCOL_VERSION_V2}|dyn={dyn.value}|"
        f"known_fraction={spec['known_fraction']}|mu_scale={spec['mean_interarrival_scale']}|"
        f"clamp=none|classify_late_for_depot_admit=1|mu={mu}|env_seed={environment_seed}"
    )
    return ordered, known, dynamic, rule, classifications


def interarrival_mean_from_releases(releases: list[tuple[str, float]]) -> float | None:
    """Empirical mean gap among positive release times (training calibration helper)."""
    times = sorted(t for _, t in releases if t > 1e-12)
    if len(times) < 2:
        if len(times) == 1:
            return float(times[0])
        return None
    gaps = [times[i] - times[i - 1] for i in range(1, len(times))]
    return sum(gaps) / len(gaps)


def build_dynamic_episode_v2(
    stem: str,
    *,
    environment_seed: int,
    policy_seed: int,
    dynamicity: Dynamicity | str = Dynamicity.MEDIUM,
    split: str = "unassigned",
) -> tuple[DynamicEpisode, list[ReleaseClassification], dict]:
    instance = load_instance(stem)
    dyn = Dynamicity(dynamicity)
    releases, known, dynamic, rule, classifications = generate_releases_v2(
        instance, environment_seed=environment_seed, dynamicity=dyn
    )
    fleet, fleet_rule, fleet_meta = select_fleet_size_v2(instance)
    depot_due = float(instance.node(instance.depot_id).window.due)
    cust_due = [float(instance.node(c).window.due) for c in instance.customer_ids()]
    horizon = max([depot_due, *cust_due]) if cust_due else depot_due
    max_replan = max(5.0, horizon / 40.0)
    t_max = horizon
    episode_id = f"{stem}|v2|{dyn.value}|env{environment_seed}|pol{policy_seed}"
    case = BaselineCase(
        episode_id,
        instance,
        list(releases),
        fleet,
        horizon,
        max_replan,
        t_max,
        (
            BENCHMARK_LABEL,
            PROTOCOL_VERSION_V2,
            f"family={_family(stem)}",
            f"n={len(instance.customer_ids())}",
            f"dyn={dyn.value}",
            f"split={split}",
        ),
    )
    episode = DynamicEpisode(
        episode_id=episode_id,
        instance_stem=stem,
        family=_family(stem),
        n_customers=len(instance.customer_ids()),
        dynamicity=dyn.value,
        environment_seed=environment_seed,
        policy_seed=policy_seed,
        fleet_size=fleet,
        fleet_rule=fleet_rule,
        horizon=horizon,
        max_replan_interval=max_replan,
        t_max=t_max,
        releases=tuple(releases),
        known_at_start=known,
        dynamic_arrivals=dynamic,
        release_rule=rule,
        instance_hash=instance_content_hash(instance),
        split=split,
        case=case,
    )
    return episode, classifications, fleet_meta


def calibrated_announcement_mean_from_train(
    train_stems: list[str],
    *,
    dynamicity: Dynamicity | str = Dynamicity.MEDIUM,
    n_realizations: int = 5,
) -> dict:
    """Fit announcement μ from training environment realizations only (no test stems)."""
    dyn = Dynamicity(dynamicity)
    gaps: list[float] = []
    n_late = 0
    n_rel = 0
    for stem in train_stems:
        for ridx in range(n_realizations):
            env = environment_seed_for(stem, ridx)
            # Re-key env seeds for v2 so v1 frozen draws stay untouched if compared.
            env_v2 = (env ^ 0xA5A5A5) & 0x7FFFFFFF
            inst = load_instance(stem)
            releases, _, _, _, classifications = generate_releases_v2(inst, environment_seed=env_v2, dynamicity=dyn)
            mu = interarrival_mean_from_releases(releases)
            if mu is not None:
                gaps.append(mu)
            n_late += sum(1 for c in classifications if c.late_for_depot_admit)
            n_rel += len(classifications)
    mean_mu = sum(gaps) / len(gaps) if gaps else 12.0
    return {
        "protocol_version": PROTOCOL_VERSION_V2,
        "dynamicity": dyn.value,
        "n_train_stems": len(train_stems),
        "n_realizations_per_stem": n_realizations,
        "n_gap_samples": len(gaps),
        "calibrated_announcement_mean": mean_mu,
        "late_for_depot_admit_rate": (n_late / n_rel) if n_rel else None,
        "policy_seed_helper": "policy_seed_for",
        "environment_seed_note": "v2 diagnostic XORs frozen v1 env seeds to avoid accidental reuse",
    }


# Re-export helpers used by diagnostics
__all__ = [
    "PROTOCOL_VERSION_V2",
    "ReleaseClassification",
    "build_dynamic_episode_v2",
    "calibrated_announcement_mean_from_train",
    "generate_releases_v2",
    "select_fleet_size_v2",
    "environment_seed_for",
    "policy_seed_for",
]
