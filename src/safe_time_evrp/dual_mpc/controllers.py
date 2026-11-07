"""Minimal receding-horizon safe dual vs safe passive controllers (toy world).

These operate on the dual-control toy decision tree, not the full FleetSimulator
geometry. They demonstrate the mechanism end-to-end with causal observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from safe_time_evrp.dual_mpc.belief import DiscreteBelief
from safe_time_evrp.dual_mpc.energy_param import SharedThetaWorld
from safe_time_evrp.dual_mpc.exact_oracle import (
    DualToyParams,
    FirstAction,
    _arrive_serve_a,
    _can_serve_c_without_charge,
    _path_feasible_for_all,
    _posterior_value_after_path,
    _safe_first_actions,
)


class DualControllerKind(str, Enum):
    SAFE_PASSIVE = "safe_passive_learning_mpc"
    SAFE_DUAL = "safe_dual_mpc"
    CLAIRVOYANT = "clairvoyant"  # privileged; evaluation only


@dataclass
class EpisodeResult:
    kind: str
    theta_star: float
    first_action: str
    served_a: bool
    served_c: bool
    reward: float
    final_belief_probs: tuple[float, ...]
    notes: tuple[str, ...]


def choose_first_action(
    kind: DualControllerKind,
    belief: DiscreteBelief,
    params: DualToyParams,
) -> FirstAction:
    safe = _safe_first_actions(params, belief)
    if not safe:
        raise RuntimeError("no safe first action")
    if kind is DualControllerKind.SAFE_PASSIVE:
        return FirstAction.EXPLOIT if FirstAction.EXPLOIT in safe else safe[0]
    if kind is DualControllerKind.SAFE_DUAL:
        scores = {a: _posterior_value_after_path(params, a, belief, safe=True) for a in safe}
        return max(scores, key=lambda a: scores[a])
    if kind is DualControllerKind.CLAIRVOYANT:
        raise ValueError("clairvoyant needs theta_star; use run_episode")
    raise ValueError(kind)


def run_episode(
    kind: DualControllerKind,
    theta_star: float,
    *,
    params: DualToyParams | None = None,
) -> EpisodeResult:
    params = params or DualToyParams()
    belief = DiscreteBelief.uniform(params.theta_support)
    world = SharedThetaWorld(theta_star=theta_star)

    if kind is DualControllerKind.CLAIRVOYANT:
        # Privileged: pick best path knowing theta_star (still must serve A).
        best = None
        best_r = float("-inf")
        for path in (FirstAction.EXPLOIT, FirstAction.INFORM):
            if not _path_feasible_for_all(
                params.exploit if path is FirstAction.EXPLOIT else params.inform,
                frozenset({theta_star}),
                params.start_soc,
            ):
                continue
            soc, t, e = _arrive_serve_a(params, path, theta_star)
            r = params.reward_a - params.energy_cost * e
            if _can_serve_c_without_charge(params, soc, t, theta_star):
                r += params.reward_c
            if r > best_r:
                best_r = r
                best = path
        assert best is not None
        first = best
    else:
        first = choose_first_action(kind, belief, params)

    feat = params.exploit if first is FirstAction.EXPLOIT else params.inform
    e_obs = world.realize(feat)
    soc, t, _ = _arrive_serve_a(params, first, theta_star)
    belief = belief.update_from_observation(feat, e_obs)
    reward = params.reward_a - params.energy_cost * e_obs
    served_c = False
    rem = belief.support_set()
    if kind is DualControllerKind.CLAIRVOYANT:
        if _can_serve_c_without_charge(params, soc, t, theta_star):
            served_c = True
            reward += params.reward_c
    else:
        ok_all = all(_can_serve_c_without_charge(params, soc, t, th) for th in rem)
        if ok_all and _can_serve_c_without_charge(params, soc, t, theta_star):
            served_c = True
            reward += params.reward_c

    return EpisodeResult(
        kind=kind.value,
        theta_star=theta_star,
        first_action=first.value,
        served_a=True,
        served_c=served_c,
        reward=reward,
        final_belief_probs=belief.probs,
        notes=(
            f"energy_obs={e_obs}",
            f"soc_after_a={soc}",
            f"time_after_a={t}",
            f"remaining_support={sorted(rem)}",
        ),
    )


def matched_comparison(params: DualToyParams | None = None) -> dict:
    """Paired comparison over both true thetas with identical priors."""
    params = params or DualToyParams()
    rows = []
    for theta in params.theta_support:
        for kind in (
            DualControllerKind.SAFE_PASSIVE,
            DualControllerKind.SAFE_DUAL,
            DualControllerKind.CLAIRVOYANT,
        ):
            ep = run_episode(kind, theta, params=params)
            rows.append(
                {
                    "theta_star": theta,
                    "kind": ep.kind,
                    "first_action": ep.first_action,
                    "served_c": ep.served_c,
                    "reward": ep.reward,
                }
            )
    dual_rewards = [r["reward"] for r in rows if r["kind"] == DualControllerKind.SAFE_DUAL.value]
    passive_rewards = [r["reward"] for r in rows if r["kind"] == DualControllerKind.SAFE_PASSIVE.value]
    return {
        "rows": rows,
        "mean_dual_reward": sum(dual_rewards) / len(dual_rewards),
        "mean_passive_reward": sum(passive_rewards) / len(passive_rewards),
        "dual_minus_passive": sum(dual_rewards) / len(dual_rewards) - sum(passive_rewards) / len(passive_rewards),
        "dual_serves_c_frac": sum(1 for r in rows if r["kind"] == DualControllerKind.SAFE_DUAL.value and r["served_c"])
        / len(dual_rewards),
        "passive_serves_c_frac": sum(
            1 for r in rows if r["kind"] == DualControllerKind.SAFE_PASSIVE.value and r["served_c"]
        )
        / len(passive_rewards),
    }
