"""Train-only arrival-rate calibration with honest sample-size reporting."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.data.dynamic_schneider import load_instance, stratified_split_small
from safe_time_evrp.data.dynamic_schneider_v2 import (
    PROTOCOL_VERSION_V2,
    build_dynamic_episode_v2,
    environment_seed_for,
    generate_releases_v2,
)


@dataclass(frozen=True)
class RateSample:
    stem: str
    realization_index: int
    n_customers: int
    horizon: float
    n_dynamic_releases: int
    n_gaps: int
    mean_gap: float | None
    rate_per_horizon: float | None  # dynamic arrivals / horizon


def calibrate_train_announcement_rate(
    *,
    dynamicity: str = "medium",
    n_realizations: int = 3,
) -> dict:
    """Fit announcement timing from training Schneider-v2 release histories only.

    Reports episode-level gap means and horizon-normalized rates. Does **not**
    claim that the number of episode-level means equals the number of independent
    interarrival draws.
    """
    splits = stratified_split_small()
    samples: list[RateSample] = []
    all_gaps: list[float] = []
    for stem in splits["train"]:
        for ridx in range(n_realizations):
            env = (environment_seed_for(stem, ridx) ^ 0xA5A5A5) & 0x7FFFFFFF
            inst = load_instance(stem)
            releases, _known, dynamic, _rule, _cls = generate_releases_v2(
                inst, environment_seed=env, dynamicity=dynamicity
            )
            depot_due = float(inst.node(inst.depot_id).window.due)
            cust_due = [float(inst.node(c).window.due) for c in inst.customer_ids()]
            horizon = max([depot_due, *cust_due]) if cust_due else depot_due
            dyn_times = sorted(t for cid, t in releases if cid in dynamic)
            gaps = [dyn_times[i] - dyn_times[i - 1] for i in range(1, len(dyn_times))]
            all_gaps.extend(gaps)
            mean_gap = sum(gaps) / len(gaps) if gaps else (dyn_times[0] if dyn_times else None)
            rate = (len(dyn_times) / horizon) if horizon > 1e-12 else None
            samples.append(
                RateSample(
                    stem=stem,
                    realization_index=ridx,
                    n_customers=len(inst.customer_ids()),
                    horizon=horizon,
                    n_dynamic_releases=len(dyn_times),
                    n_gaps=len(gaps),
                    mean_gap=mean_gap,
                    rate_per_horizon=rate,
                )
            )
    episode_means = [s.mean_gap for s in samples if s.mean_gap is not None]
    # Primary μ used by controllers: mean of positive gaps across train histories.
    calibrated_mu = sum(all_gaps) / len(all_gaps) if all_gaps else 12.0
    by_size: dict[str, list[float]] = {}
    for s in samples:
        if s.mean_gap is None:
            continue
        by_size.setdefault(str(s.n_customers), []).append(s.mean_gap)
    return {
        "protocol_version": PROTOCOL_VERSION_V2,
        "dynamicity": dynamicity,
        "train_stems": list(splits["train"]),
        "n_train_stems": len(splits["train"]),
        "n_realizations_per_stem": n_realizations,
        "n_episode_level_mean_estimates": len(episode_means),
        "n_raw_interarrival_gaps": len(all_gaps),
        "calibrated_announcement_mean": calibrated_mu,
        "mean_of_episode_means": (sum(episode_means) / len(episode_means)) if episode_means else None,
        "mean_gap_by_customer_count": {
            k: sum(v) / len(v) for k, v in sorted(by_size.items(), key=lambda kv: int(kv[0]))
        },
        "samples": [s.__dict__ for s in samples],
        "honesty_note": (
            "n_episode_level_mean_estimates counts one mean per (stem, realization). "
            "n_raw_interarrival_gaps counts individual successive dynamic-release gaps. "
            "These are not interchangeable sample sizes."
        ),
    }


def predicted_vs_realized_on_development(
    *,
    calibrated_mu: float,
    dynamicity: str = "medium",
    n_realizations: int = 2,
    n_segments: int = 4,
) -> dict:
    """Compare expected Poisson counts vs realized dynamic arrivals on development stems."""
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
            predicted = []
            for i in range(n_segments):
                lo, hi = i * seg, (i + 1) * seg
                rcount = sum(1 for t in dyn_times if lo < t <= hi)
                # Homogeneous Poisson: expected count in segment ≈ (hi-lo)/mu
                pcount = (hi - lo) / max(calibrated_mu, 1e-6)
                realized.append(rcount)
                predicted.append(pcount)
            rows.append(
                {
                    "stem": stem,
                    "realization_index": ridx,
                    "n_customers": episode.n_customers,
                    "horizon": h,
                    "n_dynamic": len(dyn_times),
                    "realized_by_segment": realized,
                    "predicted_by_segment": predicted,
                }
            )
    return {
        "calibrated_mu": calibrated_mu,
        "n_segments": n_segments,
        "n_rows": len(rows),
        "rows": rows,
    }
