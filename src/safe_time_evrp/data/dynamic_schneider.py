"""Schneider-derived dynamic EVRPTW episodes (release times only; physics unchanged).

Label: **Schneider-derived dynamic EVRPTW**.

Static Schneider files remain Euclidean E-VRPTW instances. This module adds
reproducible online announcement times without relaxing windows, battery, or
demands. Controllers never observe unreleased customers.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_suite import BaselineCase
from safe_time_evrp.data.hashing import sha256_file
from safe_time_evrp.data.paths import manifest_path, schneider_dir
from safe_time_evrp.data.schneider import iter_instance_files, parse_schneider_file
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.mpc3c.seeds import instance_content_hash, stable_seed

BENCHMARK_LABEL = "Schneider-derived dynamic EVRPTW"
PROTOCOL_VERSION = "2026-11-14.v1"

# Preregistered before any controller scores on this benchmark.
DYNAMICITY_SPECS: dict[str, dict[str, float]] = {
    "low": {"known_fraction": 0.60, "mean_interarrival_scale": 0.22},
    "medium": {"known_fraction": 0.30, "mean_interarrival_scale": 0.12},
    "high": {"known_fraction": 0.10, "mean_interarrival_scale": 0.06},
}


class Dynamicity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class SchneiderInstanceRef:
    stem: str
    path: Path
    n_customers: int
    family: str  # c | r | rc
    size_bucket: int  # 5 | 10 | 15 | 100


@dataclass(frozen=True)
class DynamicEpisode:
    """One realized announcement schedule on a Schneider instance."""

    episode_id: str
    instance_stem: str
    family: str
    n_customers: int
    dynamicity: str
    environment_seed: int
    policy_seed: int
    fleet_size: int
    fleet_rule: str
    horizon: float
    max_replan_interval: float
    t_max: float
    releases: tuple[tuple[str, float], ...]
    known_at_start: tuple[str, ...]
    dynamic_arrivals: tuple[str, ...]
    release_rule: str
    instance_hash: str
    split: str
    case: BaselineCase


def require_verified_schneider_archive() -> dict:
    """Fail clearly if the Schneider deposit is missing or hash-mismatched."""
    path = manifest_path()
    if not path.exists():
        raise FileNotFoundError(
            "data/manifests/source_manifest.json missing; run python -m safe_time_evrp.data.download"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entry = manifest.get("datasets", {}).get("schneider_evrptw", {})
    if entry.get("download_status") != "verified":
        raise RuntimeError(
            f"Schneider download_status={entry.get('download_status')!r}; "
            "run python -m safe_time_evrp.data.download && python -m safe_time_evrp.data.verify"
        )
    archive = schneider_dir() / entry["filename"]
    if not archive.is_file():
        raise FileNotFoundError(f"Schneider archive missing: {archive}")
    digest = sha256_file(archive)
    expected = entry.get("published_sha256")
    if digest != expected:
        raise RuntimeError(f"Schneider SHA-256 mismatch: got {digest}, expected {expected}")
    extracted = schneider_dir() / "extracted"
    if not extracted.is_dir():
        raise FileNotFoundError(f"Schneider extracted tree missing: {extracted}")
    return entry


def _size_bucket(stem: str) -> int | None:
    if "C5" in stem:
        return 5
    if "C10" in stem:
        return 10
    if "C15" in stem:
        return 15
    if stem.endswith("_21"):
        return 100
    return None


def _family(stem: str) -> str:
    if stem.startswith("rc"):
        return "rc"
    if stem.startswith("r"):
        return "r"
    return "c"


def list_schneider_refs(*, sizes: tuple[int, ...] = (5, 10, 15, 100)) -> list[SchneiderInstanceRef]:
    require_verified_schneider_archive()
    root = schneider_dir() / "extracted"
    out: list[SchneiderInstanceRef] = []
    for path in iter_instance_files(root):
        bucket = _size_bucket(path.stem)
        if bucket is None or bucket not in sizes:
            continue
        out.append(
            SchneiderInstanceRef(
                stem=path.stem,
                path=path,
                n_customers=bucket,
                family=_family(path.stem),
                size_bucket=bucket,
            )
        )
    return out


def stratified_split_small() -> dict[str, list[str]]:
    """Freeze train/development/test by base instance (alphabetical within stratum).

    Each (family, size) stratum has four Schneider files among the 36 small
    instances. Assignment: index0→train, index1→development, index2/3→test.
    Declared before controller evaluation.
    """
    refs = list_schneider_refs(sizes=(5, 10, 15))
    by_stratum: dict[tuple[str, int], list[SchneiderInstanceRef]] = {}
    for ref in refs:
        by_stratum.setdefault((ref.family, ref.size_bucket), []).append(ref)
    train: list[str] = []
    development: list[str] = []
    test: list[str] = []
    for key in sorted(by_stratum):
        group = sorted(by_stratum[key], key=lambda r: r.stem)
        if len(group) != 4:
            raise RuntimeError(f"expected 4 instances in stratum {key}, got {len(group)}")
        train.append(group[0].stem)
        development.append(group[1].stem)
        test.extend([group[2].stem, group[3].stem])
    return {"train": train, "development": development, "test": test}


def scalability_instance_stems() -> tuple[str, ...]:
    """Predeclared 100-customer stems chosen before seeing results."""
    return ("c101_21", "r101_21", "rc101_21")


def select_fleet_size(instance: Instance) -> tuple[int, str]:
    """Nontrivial fleet from load and customer count; never silently inflate capacity."""
    customers = instance.customer_ids()
    n = len(customers)
    demand = sum(float(instance.node(cid).demand) for cid in customers)
    cap = float(instance.vehicle_type.load_capacity)
    by_load = max(1, int(math.ceil(demand / cap))) if cap > 0 else 1
    by_count = max(1, int(math.ceil(n / 5.0)))
    fleet = min(6, max(by_load, by_count))
    rule = f"min(6, max(ceil(demand/C)={by_load}, ceil(n/5)={by_count}))"
    return fleet, rule


def latest_feasible_announce_time(instance: Instance, customer_id: str) -> float:
    """Latest time a request can be announced and still admit a depot→customer start-by-due trip.

    Does not change windows. If already impossible from the depot at t=0, returns 0.0
    (announce at start; plant may still find the customer unserviceable).
    """
    node = instance.node(customer_id)
    depot = instance.depot_id
    travel = float(instance.arc(depot, customer_id).travel_time)
    latest = float(node.window.due) - float(node.service_time) - travel
    return max(0.0, latest)


def _lcg(state: int) -> tuple[int, float]:
    state = (1_103_515_245 * state + 12_345) & 0x7FFFFFFF
    return state, state / 0x7FFFFFFF


def _exponential_gap(mean: float, u: float) -> float:
    u = min(max(u, 1e-12), 1.0 - 1e-12)
    return -mean * math.log(u)


def generate_releases(
    instance: Instance,
    *,
    environment_seed: int,
    dynamicity: Dynamicity | str,
) -> tuple[list[tuple[str, float]], tuple[str, ...], tuple[str, ...], str]:
    """Draw announcement times from ``environment_seed`` only (not policy seed)."""
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
    # Ensure high dynamicity has at least one online arrival when n>=2.
    if dyn is Dynamicity.HIGH and len(order) >= 2:
        n_known = min(n_known, len(order) - 1)
    known = tuple(order[:n_known])
    dynamic = tuple(order[n_known:])

    releases: dict[str, float] = {cid: 0.0 for cid in known}
    t = 0.0
    for cid in dynamic:
        state, u = _lcg(state)
        t += _exponential_gap(mu, u)
        latest = latest_feasible_announce_time(instance, cid)
        releases[cid] = float(min(t, latest))

    ordered = sorted(releases.items(), key=lambda kv: (kv[1], kv[0]))
    rule = (
        f"{BENCHMARK_LABEL}|dyn={dyn.value}|known_fraction={spec['known_fraction']}|"
        f"mu_scale={spec['mean_interarrival_scale']}|clamp=min(poisson_t, latest_depot_admit)|"
        f"env_seed={environment_seed}"
    )
    return ordered, known, dynamic, rule


def load_instance(stem: str) -> Instance:
    require_verified_schneider_archive()
    matches = [p for p in iter_instance_files(schneider_dir() / "extracted") if p.stem == stem]
    if not matches:
        raise FileNotFoundError(f"Schneider instance not found: {stem}")
    return parse_schneider_file(matches[0])


def build_dynamic_episode(
    stem: str,
    *,
    environment_seed: int,
    policy_seed: int,
    dynamicity: Dynamicity | str = Dynamicity.MEDIUM,
    split: str = "unassigned",
) -> DynamicEpisode:
    instance = load_instance(stem)
    dyn = Dynamicity(dynamicity)
    releases, known, dynamic, rule = generate_releases(instance, environment_seed=environment_seed, dynamicity=dyn)
    fleet, fleet_rule = select_fleet_size(instance)
    depot_due = float(instance.node(instance.depot_id).window.due)
    cust_due = [float(instance.node(c).window.due) for c in instance.customer_ids()]
    horizon = max([depot_due, *cust_due]) if cust_due else depot_due
    max_replan = max(5.0, horizon / 40.0)
    t_max = horizon
    episode_id = f"{stem}|{dyn.value}|env{environment_seed}|pol{policy_seed}"
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
            f"family={_family(stem)}",
            f"n={len(instance.customer_ids())}",
            f"dyn={dyn.value}",
            f"split={split}",
        ),
    )
    return DynamicEpisode(
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


def environment_seed_for(stem: str, realization_index: int) -> int:
    return stable_seed("schneider_dyn_env", stem, str(realization_index), PROTOCOL_VERSION)


def policy_seed_for(stem: str, realization_index: int, controller_name: str) -> int:
    """Policy RNG seed. Same across controllers for a fixed realization index.

    Controllers still receive the identical integer so ALNS/forecast draws that
    depend only on ``seed`` are aligned; the environment realization is separate.
    """
    _ = controller_name  # reserved for audits; shared policy seed by design
    return stable_seed("schneider_dyn_policy", stem, str(realization_index), PROTOCOL_VERSION)


def charger_count(instance: Instance) -> int:
    return sum(1 for n in instance.nodes.values() if n.kind is NodeKind.CHARGER)
