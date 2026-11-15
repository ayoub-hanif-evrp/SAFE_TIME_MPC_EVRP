"""Decision-focused action advantage estimation (Stage 3 foundation).

Target: A(o,a) = E[return|o,a] - E[return|o,incumbent] under shared scenarios.
Training uses train/development states only. Not a neural network by default.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.models.state import Decision, Observation
from safe_time_evrp.mpc3c.forecast import ForecastCustomer
from safe_time_evrp.mpc_central.flexibility_features import flexibility_snapshot
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value


@dataclass(frozen=True)
class AdvantageEstimate:
    name: str
    paired_delta: float | None
    feature_score: float
    n_scenarios: int
    notes: tuple[str, ...]


def feature_advantage_score(
    observation: Observation,
    candidate: Decision,
    incumbent: Decision,
    *,
    expected_remaining: float,
) -> float:
    """Interpretable hand-designed relative score (baseline for learned models)."""
    sc = flexibility_snapshot(observation, candidate)
    si = flexibility_snapshot(observation, incumbent)
    # Prefer preserving min SoC and idle capacity when future demand remains.
    bat = 0.05 * (sc.min_battery - si.min_battery)
    idle = 0.2 * (sc.n_idle_at_depot - si.n_idle_at_depot)
    charge = 0.1 * (sc.charge_legs - si.charge_legs) * (1.0 if expected_remaining > 0 else -0.5)
    accept = 0.15 * (len(candidate.newly_accepted) - len(incumbent.newly_accepted))
    return bat + idle + charge + accept


def paired_causal_advantage(
    instance,
    observation: Observation,
    name: str,
    candidate: Decision,
    incumbent: Decision,
    scenarios: list[list[ForecastCustomer]],
    *,
    horizon: float,
    max_replan_interval: float = 5.0,
    max_events: int = 80,
    energy=None,
) -> AdvantageEstimate:
    """CRN paired delta under the same scenario list (causal objective)."""
    if not scenarios:
        scenarios = [[]]
    v_c, s_c = expected_rollout_value(
        instance,
        observation,
        candidate,
        scenarios,
        horizon=horizon,
        scoring_mode="causal",
        max_replan_interval=max_replan_interval,
        max_events=max_events,
        energy=energy,
    )
    v_i, s_i = expected_rollout_value(
        instance,
        observation,
        incumbent,
        scenarios,
        horizon=horizon,
        scoring_mode="causal",
        max_replan_interval=max_replan_interval,
        max_events=max_events,
        energy=energy,
    )
    ok = all(s.replay_ok for s in s_c) and all(s.replay_ok for s in s_i)
    delta = (v_c - v_i) if ok else None
    feat = feature_advantage_score(observation, candidate, incumbent, expected_remaining=0.0)
    notes = ("paired_causal",) if ok else ("fail_closed_invalid_scenario",)
    return AdvantageEstimate(
        name=name,
        paired_delta=delta,
        feature_score=feat,
        n_scenarios=len(scenarios),
        notes=notes,
    )


def screen_by_features(
    observation: Observation,
    incumbent: Decision,
    named: list[tuple[str, Decision]],
    *,
    expected_remaining: float,
    keep: int = 3,
) -> list[tuple[str, Decision, float]]:
    scored = [
        (n, d, feature_advantage_score(observation, d, incumbent, expected_remaining=expected_remaining))
        for n, d in named
    ]
    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:keep]
