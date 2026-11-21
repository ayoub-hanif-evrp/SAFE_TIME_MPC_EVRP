"""Finite-demand / finite-active-period anonymous forecast model.

Corrects the homogeneous Poisson-over-full-horizon approximation that produced
large phantom populations after Schneider-derived demand had ended.

Information boundary:
- Spatial/service atoms and lead-time/window structure from **training** only.
- Finite remaining count uses the public static instance customer count minus
  already-announced customers (Schneider EVRPTW-D convention: customer *set*
  known, announcement *times* stochastic). Unreleased customer attributes are
  never copied into forecast nodes.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    PROTOCOL_VERSION_V2,
    build_dynamic_episode_v2,
    environment_seed_for,
)
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc3c.forecast import ForecastCustomer, TrainDemandAtom, _lcg
from safe_time_evrp.mpc3c.seeds import stable_seed


@dataclass(frozen=True)
class LeadTimeAtom:
    """Announcement-to-window structure from training releases."""

    lead_ready: float  # window.ready - announcement (can be negative if late)
    span: float  # due - ready (>= small epsilon)


@dataclass(frozen=True)
class SizeClassStats:
    n_customers: int
    n_episodes: int
    mean_dynamic: float
    mean_known: float
    # Empirical announcement times as fractions of episode horizon (dynamic only).
    announce_fracs: tuple[float, ...]
    # Fraction of dynamic arrivals with announce_frac <= q for q in (0.25, 0.5, 0.75, 1.0)
    cdf_quartiles: tuple[float, float, float, float]
    # Demand-active end: empirical 0.95 quantile of announce_frac (or 1.0).
    active_end_frac: float
    lead_atoms: tuple[LeadTimeAtom, ...]


@dataclass(frozen=True)
class FiniteDemandModel:
    """Train-fitted finite population + active-period forecast prior."""

    train_atoms: tuple[TrainDemandAtom, ...]
    by_size: dict[int, SizeClassStats]
    pooled: SizeClassStats
    protocol_version: str = PROTOCOL_VERSION_V2
    model_id: str = "finite_demand_v1"

    def stats_for(self, n_customers: int) -> SizeClassStats:
        if n_customers in self.by_size:
            return self.by_size[n_customers]
        # Nearest size class.
        if not self.by_size:
            return self.pooled
        nearest = min(self.by_size.keys(), key=lambda k: abs(k - n_customers))
        return self.by_size[nearest]


def _announced_ids(observation: Observation) -> set[str]:
    return (
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.completed)
        | set(observation.rejected)
        | set(observation.in_service)
        | set(observation.deferred)
    )


def remaining_announcement_count(instance: Instance, observation: Observation) -> int:
    """Public finite remaining using the formal public population size.

    Prefer ``observation.public_customer_count`` (information contract). Fall back
    to ``len(instance.customer_ids())`` only when that field is unset (legacy tests).
    Unreleased customer *attributes* are never read here.
    """
    pub = getattr(observation, "public_customer_count", None)
    if pub is not None:
        total = int(pub)
    else:
        total = len(instance.customer_ids())
    seen = len(_announced_ids(observation))
    return max(0, total - seen)


@dataclass(frozen=True)
class FiniteDemandTrainEpisode:
    """One training release trajectory for finite-demand fitting (family-agnostic)."""

    n_customers: int
    horizon: float
    releases: list[tuple[str, float]]
    dynamic_arrivals: set[str]
    known_at_start: set[str]
    instance: Instance


def _size_class_stats(n: int, raw: dict) -> SizeClassStats:
    fracs = sorted(raw["fracs"])
    leads = tuple(raw["leads"]) or (LeadTimeAtom(0.0, 30.0),)

    def _cdf(q: float) -> float:
        if not fracs:
            return 0.0
        return sum(1 for f in fracs if f <= q) / len(fracs)

    active = fracs[int(0.95 * (len(fracs) - 1))] if fracs else 1.0
    return SizeClassStats(
        n_customers=n,
        n_episodes=raw["n_episodes"],
        mean_dynamic=sum(raw["dynamic_counts"]) / max(raw["n_episodes"], 1),
        mean_known=sum(raw["known_counts"]) / max(raw["n_episodes"], 1),
        announce_fracs=tuple(fracs),
        cdf_quartiles=(_cdf(0.25), _cdf(0.5), _cdf(0.75), _cdf(1.0)),
        active_end_frac=float(active),
        lead_atoms=leads,
    )


def fit_finite_demand_model_from_episodes(
    episodes: list[FiniteDemandTrainEpisode],
    *,
    train_atoms: tuple[TrainDemandAtom, ...],
    model_id: str,
    protocol_version: str = PROTOCOL_VERSION_V2,
) -> FiniteDemandModel:
    """Fit finite-demand timing/lead stats from explicit train episodes (any family)."""
    by_size_raw: dict[int, dict] = {}
    for ep in episodes:
        n = int(ep.n_customers)
        h = max(float(ep.horizon), 1e-9)
        dyn = set(ep.dynamic_arrivals)
        known = set(ep.known_at_start)
        fracs: list[float] = []
        leads: list[LeadTimeAtom] = []
        inst = ep.instance
        for cid, t in ep.releases:
            if cid not in dyn:
                continue
            fracs.append(min(1.0, max(0.0, float(t) / h)))
            node = inst.node(cid)
            span = max(float(node.window.due) - float(node.window.ready), 1.0)
            leads.append(LeadTimeAtom(lead_ready=float(node.window.ready) - float(t), span=span))
        bucket = by_size_raw.setdefault(
            n,
            {
                "n_episodes": 0,
                "dynamic_counts": [],
                "known_counts": [],
                "fracs": [],
                "leads": [],
            },
        )
        bucket["n_episodes"] += 1
        bucket["dynamic_counts"].append(len(dyn))
        bucket["known_counts"].append(len(known))
        bucket["fracs"].extend(fracs)
        bucket["leads"].extend(leads)

    by_size = {n: _size_class_stats(n, raw) for n, raw in by_size_raw.items()}
    pooled_raw = {
        "n_episodes": sum(r["n_episodes"] for r in by_size_raw.values()) if by_size_raw else 0,
        "dynamic_counts": [c for r in by_size_raw.values() for c in r["dynamic_counts"]],
        "known_counts": [c for r in by_size_raw.values() for c in r["known_counts"]],
        "fracs": [f for r in by_size_raw.values() for f in r["fracs"]],
        "leads": [x for r in by_size_raw.values() for x in r["leads"]],
    }
    pooled = _size_class_stats(0, pooled_raw)
    return FiniteDemandModel(
        train_atoms=train_atoms,
        by_size=by_size,
        pooled=pooled,
        protocol_version=protocol_version,
        model_id=model_id,
    )


def fit_finite_demand_model(
    *,
    dynamicity: str = "medium",
    n_realizations: int = 3,
) -> FiniteDemandModel:
    """Fit finite-demand timing/lead stats from Schneider-v2 **training** releases only."""
    splits = stratified_split_small()
    from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals

    spatial = fit_empirical_arrivals([load_instance(s) for s in splits["train"]])
    episodes: list[FiniteDemandTrainEpisode] = []
    for stem in splits["train"]:
        for ridx in range(n_realizations):
            env = (environment_seed_for(stem, ridx) ^ 0xA5A5A5) & 0x7FFFFFFF
            episode, _cls, _fleet = build_dynamic_episode_v2(
                stem,
                environment_seed=env,
                policy_seed=0,
                dynamicity=dynamicity,
                split="train",
            )
            episodes.append(
                FiniteDemandTrainEpisode(
                    n_customers=episode.n_customers,
                    horizon=float(episode.horizon),
                    releases=list(episode.releases),
                    dynamic_arrivals=set(episode.dynamic_arrivals),
                    known_at_start=set(episode.known_at_start),
                    instance=episode.case.instance,
                )
            )
    return fit_finite_demand_model_from_episodes(
        episodes,
        train_atoms=spatial.train_atoms,
        model_id=f"finite_demand_v1;family=schneider;train={len(splits['train'])};dyn={dynamicity}",
    )


def expected_remaining_given_public(
    model: FiniteDemandModel,
    instance: Instance,
    observation: Observation,
    *,
    horizon: float,
) -> dict:
    """Calibrated remaining-count estimate from public state + train timing."""
    pub = getattr(observation, "public_customer_count", None)
    n = int(pub) if pub is not None else len(instance.customer_ids())
    remaining_hard = remaining_announcement_count(instance, observation)
    stats = model.stats_for(n)
    now = float(observation.time)
    h = max(float(horizon), 1e-9)
    t_frac = min(1.0, max(0.0, now / h))
    # Soft prior: among train dynamic arrivals, fraction still after t_frac.
    fracs = stats.announce_fracs
    if fracs:
        survival = sum(1 for f in fracs if f > t_frac + 1e-12) / len(fracs)
    else:
        survival = 0.0 if t_frac >= stats.active_end_frac else 1.0
    # After empirical active end, force near-zero phantom mass.
    if t_frac >= stats.active_end_frac - 1e-12:
        survival = 0.0
    prior_remaining = stats.mean_dynamic * survival
    # Cap by hard finite population remaining.
    expected = min(float(remaining_hard), prior_remaining) if remaining_hard else 0.0
    # If hard remaining is positive but prior says demand ended, trust active-end.
    if survival <= 1e-12:
        expected = 0.0
    return {
        "n_customers": n,
        "remaining_hard_cap": remaining_hard,
        "t_frac": t_frac,
        "active_end_frac": stats.active_end_frac,
        "survival": survival,
        "prior_remaining": prior_remaining,
        "expected_remaining": expected,
    }


def _quartile_bins(values: list[float], n_bins: int = 4) -> list[list[float]]:
    """Split sorted values into up to ``n_bins`` non-empty quantile bins."""
    if not values:
        return [[] for _ in range(n_bins)]
    xs = sorted(values)
    bins: list[list[float]] = [[] for _ in range(n_bins)]
    for i, v in enumerate(xs):
        bins[min(n_bins - 1, (i * n_bins) // len(xs))].append(v)
    # Drop empties but keep at least one bin for indexing safety.
    nonempty = [b for b in bins if b]
    return nonempty or [[]]


def _spatial_quadrant_bins(atoms: tuple[TrainDemandAtom, ...]) -> list[tuple[TrainDemandAtom, ...]]:
    """Partition train atoms into up to 4 spatial quadrants about median (x, y)."""
    if not atoms:
        return [()]
    xs = sorted(a.x for a in atoms)
    ys = sorted(a.y for a in atoms)
    mx = xs[len(xs) // 2]
    my = ys[len(ys) // 2]
    buckets: list[list[TrainDemandAtom]] = [[], [], [], []]
    for a in atoms:
        qi = (0 if a.x <= mx else 1) + (0 if a.y <= my else 2)
        buckets[qi].append(a)
    nonempty = [tuple(b) for b in buckets if b]
    return nonempty or [atoms]


def scenario_set_diversity(scenarios: list[list[ForecastCustomer]]) -> dict[str, float]:
    """Pairwise diversity of announce times and locations across scenarios."""
    n = len(scenarios)
    if n < 2:
        return {"n_scenarios": float(n), "mean_announce_l1": 0.0, "mean_xy_l1": 0.0, "score": 0.0}
    ann = []
    xy = []
    for i in range(n):
        for j in range(i + 1, n):
            ai = sorted(float(c.announcement_time) for c in scenarios[i])
            aj = sorted(float(c.announcement_time) for c in scenarios[j])
            m = max(len(ai), len(aj), 1)
            ai = ai + [ai[-1] if ai else 0.0] * (m - len(ai))
            aj = aj + [aj[-1] if aj else 0.0] * (m - len(aj))
            ann.append(sum(abs(a - b) for a, b in zip(ai, aj)) / m)
            xi = sorted((float(c.x), float(c.y)) for c in scenarios[i])
            xj = sorted((float(c.x), float(c.y)) for c in scenarios[j])
            mxy = max(len(xi), len(xj), 1)
            xi = xi + [xi[-1] if xi else (0.0, 0.0)] * (mxy - len(xi))
            xj = xj + [xj[-1] if xj else (0.0, 0.0)] * (mxy - len(xj))
            xy.append(
                sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(xi, xj)) / mxy
            )
    mean_ann = sum(ann) / len(ann)
    mean_xy = sum(xy) / len(xy)
    return {
        "n_scenarios": float(n),
        "mean_announce_l1": mean_ann,
        "mean_xy_l1": mean_xy,
        "score": mean_ann + mean_xy,
    }


def sample_finite_demand_scenarios(
    model: FiniteDemandModel,
    observation: Observation,
    instance: Instance,
    *,
    horizon: float,
    n_scenarios: int = 2,
    seed: int = 0,
    max_customers: int = 16,
    sample_mode: str = "stratified",
) -> list[list[ForecastCustomer]]:
    """Draw anonymous futures with finite remaining count and realistic windows.

    Announcement times are sampled from the train empirical distribution conditional
    on being in ``(now, now+H]`` and before the demand-active end. Service windows
    use train lead-time atoms (ready = announce + lead, due = ready + span), not
    ``ready := announce``.

    ``sample_mode``:
    - ``stratified`` (default): cover announce-time quartile × spatial quadrant strata
      (descriptive / low-discrepancy style) so small scenario sets stay diverse.
    - ``iid``: independent LCG draws (legacy ablation).
    """
    meta = expected_remaining_given_public(model, instance, observation, horizon=horizon)
    expected = float(meta["expected_remaining"])
    now = float(observation.time)
    h = max(float(horizon), 0.0)
    n_sc = max(1, int(n_scenarios))
    if h <= 1e-12 or expected <= 1e-9 or not model.train_atoms:
        return [[] for _ in range(n_sc)]

    n = int(meta["n_customers"])
    stats = model.stats_for(n)
    active_end = float(stats.active_end_frac) * max(horizon, 1e-9)
    hi = min(now + h, active_end)
    future_fracs = [f for f in stats.announce_fracs if now < f * max(horizon, 1e-9) <= hi + 1e-12]
    known = _announced_ids(observation)
    bucket = int(round(now * 10.0))
    mode = (sample_mode or "stratified").strip().lower()
    time_bins = _quartile_bins(future_fracs, n_bins=min(4, max(1, n_sc))) if future_fracs else [[]]
    space_bins = _spatial_quadrant_bins(model.train_atoms)
    sorted_fracs = sorted(future_fracs) if future_fracs else []
    out: list[list[ForecastCustomer]] = []
    for s_idx in range(n_sc):
        state = stable_seed(
            "finite_demand_fc",
            str(seed),
            str(s_idx),
            str(bucket),
            f"exp={expected:.4f}",
            mode,
            model.model_id[:48],
        )
        state, _u_n = _lcg(state)
        state, u_extra = _lcg(state)
        n_draw = int(round(expected + (u_extra - 0.5)))
        n_draw = max(0, min(n_draw, int(meta["remaining_hard_cap"]), max_customers))
        # Descriptive strata: scenario s owns time quantile (s+0.5)/n and spatial bin s.
        t_bin = time_bins[s_idx % len(time_bins)]
        s_bin = space_bins[s_idx % len(space_bins)]
        items: list[ForecastCustomer] = []
        for k in range(n_draw):
            if not future_fracs:
                break
            if mode == "iid":
                state, u_pick_t = _lcg(state)
                frac = future_fracs[int(u_pick_t * len(future_fracs)) % len(future_fracs)]
            else:
                # First customer: exact descriptive quantile; later: jitter inside owned bin.
                if k == 0 and sorted_fracs:
                    q = (s_idx + 0.5) / n_sc
                    frac = sorted_fracs[min(len(sorted_fracs) - 1, int(q * len(sorted_fracs)))]
                else:
                    pool = t_bin if t_bin else future_fracs
                    state, u_pick_t = _lcg(state)
                    frac = pool[int(u_pick_t * len(pool)) % len(pool)]
            t_ann = float(frac) * max(horizon, 1e-9)
            if t_ann <= now + 1e-12 or t_ann > hi + 1e-12:
                continue
            if mode == "iid":
                atom_pool = model.train_atoms
            else:
                atom_pool = s_bin if s_bin else model.train_atoms
            state, u_atom = _lcg(state)
            atom = atom_pool[int(u_atom * len(atom_pool)) % len(atom_pool)]
            state, u_lead = _lcg(state)
            lead = stats.lead_atoms[int(u_lead * len(stats.lead_atoms)) % len(stats.lead_atoms)]
            state, jx = _lcg(state)
            state, jy = _lcg(state)
            # Stratified: smaller jitter so scenario centroids stay separated.
            jitter = 0.15 if mode != "iid" else 0.5
            x = atom.x + (jx - 0.5) * jitter
            y = atom.y + (jy - 0.5) * jitter
            ready = float(t_ann) + float(lead.lead_ready)
            if ready < t_ann:
                ready = float(t_ann)
            due = ready + max(float(lead.span), 1.0)
            cid = f"syn_fd_s{s_idx}_{k}_t{bucket}"
            if cid in known:
                continue
            items.append(
                ForecastCustomer(
                    customer_id=cid,
                    ready_time=ready,
                    due_time=due,
                    x=x,
                    y=y,
                    demand=max(atom.demand, 0.01),
                    service_time=max(atom.service_time, 0.0),
                    source=f"finite_demand_scenario_{s_idx}_{mode}",
                    announcement_time=float(t_ann),
                )
            )
        out.append(items)
    return out


def sample_finite_demand_scenarios_crn(
    model: FiniteDemandModel,
    observation: Observation,
    instance: Instance,
    *,
    horizon: float,
    n_scenarios: int,
    seed: int,
    sample_mode: str = "stratified",
) -> list[list[ForecastCustomer]]:
    """CRN wrapper (single model) — shared seeds across scenario indices."""
    return sample_finite_demand_scenarios(
        model,
        observation,
        instance,
        horizon=horizon,
        n_scenarios=n_scenarios,
        seed=seed,
        sample_mode=sample_mode,
    )


def calibration_report_finite_vs_poisson(
    *,
    finite: FiniteDemandModel,
    poisson_mu: float,
    dynamicity: str = "medium",
    n_realizations: int = 2,
    n_segments: int = 4,
    poisson_cap: int = 32,
) -> dict:
    """Compare predicted vs realized counts: finite model vs old Poisson-over-horizon."""
    splits = stratified_split_small()
    rows = []
    for stem in splits["development"]:
        for ridx in range(n_realizations):
            env = (environment_seed_for(stem, ridx) ^ 0xA5A5A5) & 0x7FFFFFFF
            episode, _cls, _fleet = build_dynamic_episode_v2(
                stem,
                environment_seed=env,
                policy_seed=0,
                dynamicity=dynamicity,
                split="development",
            )
            dyn_times = sorted(t for cid, t in episode.releases if cid in episode.dynamic_arrivals)
            h = episode.horizon
            seg = h / n_segments if h > 0 else 1.0
            realized = []
            pred_finite = []
            pred_poisson = []
            for i in range(n_segments):
                lo, hi = i * seg, (i + 1) * seg
                rcount = sum(1 for t in dyn_times if lo < t <= hi)
                # Finite: expected mass in segment from empirical fracs * mean_dynamic.
                stats = finite.stats_for(episode.n_customers)
                if stats.announce_fracs:
                    mass = sum(1 for f in stats.announce_fracs if lo / h < f <= hi / h) / len(stats.announce_fracs)
                    p_f = stats.mean_dynamic * mass
                else:
                    p_f = 0.0
                # Old homogeneous Poisson rate 1/mu over full segment, uncapped phantom risk.
                p_p = (hi - lo) / max(poisson_mu, 1e-6)
                p_p = min(p_p, float(poisson_cap))
                realized.append(rcount)
                pred_finite.append(p_f)
                pred_poisson.append(p_p)
            rows.append(
                {
                    "stem": stem,
                    "realization_index": ridx,
                    "n_customers": episode.n_customers,
                    "realized_by_segment": realized,
                    "predicted_finite_by_segment": pred_finite,
                    "predicted_poisson_by_segment": pred_poisson,
                    "realized_total": sum(realized),
                    "predicted_finite_total": sum(pred_finite),
                    "predicted_poisson_total": sum(pred_poisson),
                }
            )

    def _sum_field(key: str) -> float:
        return float(sum(r[key] for r in rows))

    seg_errs_f: list[float] = []
    seg_errs_p: list[float] = []
    by_size: dict[str, dict] = {}
    for r in rows:
        for a, b in zip(r["realized_by_segment"], r["predicted_finite_by_segment"], strict=True):
            seg_errs_f.append(abs(float(a) - float(b)))
        for a, b in zip(r["realized_by_segment"], r["predicted_poisson_by_segment"], strict=True):
            seg_errs_p.append(abs(float(a) - float(b)))
        key = str(r["n_customers"])
        bucket = by_size.setdefault(key, {"realized": 0.0, "finite": 0.0, "poisson": 0.0, "n": 0})
        bucket["realized"] += float(r["realized_total"])
        bucket["finite"] += float(r["predicted_finite_total"])
        bucket["poisson"] += float(r["predicted_poisson_total"])
        bucket["n"] += 1

    return {
        "protocol_version": PROTOCOL_VERSION_V2,
        "n_rows": len(rows),
        "sum_realized": _sum_field("realized_total"),
        "sum_predicted_finite": _sum_field("predicted_finite_total"),
        "sum_predicted_poisson": _sum_field("predicted_poisson_total"),
        "finite_over_realized_ratio": (_sum_field("predicted_finite_total") / max(_sum_field("realized_total"), 1e-9)),
        "poisson_over_realized_ratio": (
            _sum_field("predicted_poisson_total") / max(_sum_field("realized_total"), 1e-9)
        ),
        "mean_abs_segment_error_finite": (sum(seg_errs_f) / len(seg_errs_f)) if seg_errs_f else None,
        "mean_abs_segment_error_poisson": (sum(seg_errs_p) / len(seg_errs_p)) if seg_errs_p else None,
        "totals_by_customer_count": by_size,
        "rows": rows,
        "honesty_note": (
            "Pooled predicted==realized totals can be partly mechanical when N and "
            "dynamicity fractions are known. Prefer segment MAE, size-stratified totals, "
            "and temporal survival calibration over the pooled ratio alone."
        ),
        "note": (
            "Finite model uses train empirical announce-time fractions * mean dynamic count. "
            "Poisson uses homogeneous rate over the full horizon (old misspecification)."
        ),
    }
