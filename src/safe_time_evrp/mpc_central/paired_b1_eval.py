"""Paired B1-reference evaluation for baseline-anchored switching MPC.

For each candidate and each shared forecast scenario, evaluate BOTH the candidate
and the executable B1 decision under identical causal recourse. Invalid replay
scores never enter the comparison (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation
from safe_time_evrp.mpc3c.forecast import ForecastCustomer
from safe_time_evrp.mpc_central.causal_plant import DISTANCE_PENALTY, SERVICE_REWARD, UNFULFILLED_PENALTY
from safe_time_evrp.mpc_central.counterfactual_actions import (
    FirstActionKey,
    generate_counterfactual_actions,
    sanitize_newly_accepted,
    sanitize_rejects,
    sanitize_routes,
)
from safe_time_evrp.mpc_central.scenario_rollout import rollout_candidate

# A priori outcome bound for paired deltas (value units). Not fitted on Phase 3E seeds.
DELTA_BOUND = SERVICE_REWARD + UNFULFILLED_PENALTY + 50.0 * DISTANCE_PENALTY


@dataclass(frozen=True)
class ScenarioPairDelta:
    scenario_index: int
    candidate_value: float
    b1_value: float
    delta: float
    candidate_completed: tuple[str, ...]
    b1_completed: tuple[str, ...]
    candidate_au: tuple[str, ...]
    b1_au: tuple[str, ...]
    candidate_distance: float
    b1_distance: float
    candidate_replay_ok: bool
    b1_replay_ok: bool
    valid_for_comparison: bool


@dataclass
class PairedCandidateReport:
    name: str
    candidate: Decision
    b1: Decision
    commitment_ok: bool
    commitment_reasons: list[str] = field(default_factory=list)
    pairs: list[ScenarioPairDelta] = field(default_factory=list)
    mean_delta: float | None = None
    min_delta: float | None = None
    hoeffding_lcb: float | None = None
    notes: list[str] = field(default_factory=list)


def build_b1_decision(
    instance: Instance,
    observation: Observation,
    *,
    horizon: float,
    alns_iterations: int,
    alns_time: float,
    seed: int,
    energy: NominalLinearEnergy | None = None,
) -> Decision:
    model = energy or NominalLinearEnergy()
    b1 = FullValidationAlnsMpc(
        instance,
        horizon,
        energy=model,
        iterations=alns_iterations,
        time_limit_seconds=alns_time,
        seed=seed,
    )
    d = b1.decide(observation, "b1_reference")
    routes = sanitize_routes(observation, d.routes)
    newly = sanitize_newly_accepted(observation, list(d.newly_accepted))
    rejected = sanitize_rejects(observation, [c for c in d.rejected if c not in newly])
    accepted = list(observation.accepted)
    for c in newly:
        if c not in accepted:
            accepted.append(c)
    return Decision(
        time=observation.time,
        routes=routes,
        accepted=accepted,
        newly_accepted=newly,
        rejected=rejected,
        deferred=list(d.deferred),
        fallback_used=d.fallback_used,
        no_feasible_continuation=d.no_feasible_continuation,
        horizon_extended=d.horizon_extended,
        planned_service=list(d.planned_service),
        total_distance=d.total_distance,
        total_charge_time=d.total_charge_time,
        optimize_seconds=d.optimize_seconds,
        trigger="b1_reference",
        locked_destinations=dict(d.locked_destinations),
        notes=list(d.notes) + ["b1_reference"],
    )


def _decompose_forecast_completed(
    observation: Observation, completed: tuple[str, ...], forecasts: list[ForecastCustomer]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    public = (
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.completed)
        | set(observation.in_service)
        | set(observation.deferred)
        | set(observation.rejected)
    )
    forecast_ids = {fc.customer_id for fc in forecasts}
    real = tuple(sorted(c for c in completed if c in public))
    fc_done = tuple(sorted(c for c in completed if c in forecast_ids and c not in public))
    return real, fc_done


def evaluate_paired_candidate(
    instance: Instance,
    observation: Observation,
    name: str,
    candidate: Decision,
    b1: Decision,
    scenario_forecasts: list[list[ForecastCustomer]],
    *,
    horizon: float,
    max_replan_interval: float = 5.0,
    max_events: int = 200,
    energy: NominalLinearEnergy | None = None,
    alpha: float = 0.1,
) -> PairedCandidateReport:
    model = energy or NominalLinearEnergy()
    public = make_public_snapshot(instance, observation, horizon).instance
    report = validate_continuation(
        public,
        observation,
        candidate.routes,
        energy=model,
        require_new=frozenset(candidate.newly_accepted),
    )
    out = PairedCandidateReport(
        name=name,
        candidate=candidate,
        b1=b1,
        commitment_ok=report.ok,
        commitment_reasons=list(report.reasons),
    )
    if not report.ok:
        out.notes.append("commitment_gate_failed")
        return out

    pairs: list[ScenarioPairDelta] = []
    for i, fcs in enumerate(scenario_forecasts):
        cand_score = rollout_candidate(
            instance,
            observation,
            candidate,
            fcs,
            horizon=horizon,
            max_replan_interval=max_replan_interval,
            max_events=max_events,
            energy=model,
        )
        b1_score = rollout_candidate(
            instance,
            observation,
            b1,
            fcs,
            horizon=horizon,
            max_replan_interval=max_replan_interval,
            max_events=max_events,
            energy=model,
        )
        valid = cand_score.replay_ok and b1_score.replay_ok
        delta = (cand_score.value - b1_score.value) if valid else float("nan")
        pairs.append(
            ScenarioPairDelta(
                scenario_index=i,
                candidate_value=cand_score.value,
                b1_value=b1_score.value,
                delta=delta,
                candidate_completed=cand_score.completed,
                b1_completed=b1_score.completed,
                candidate_au=cand_score.accepted_unfulfilled,
                b1_au=b1_score.accepted_unfulfilled,
                candidate_distance=cand_score.executed_distance,
                b1_distance=b1_score.executed_distance,
                candidate_replay_ok=cand_score.replay_ok,
                b1_replay_ok=b1_score.replay_ok,
                valid_for_comparison=valid,
            )
        )
        # Attach decomposition into notes for audit (real vs forecast completions).
        real_c, fc_c = _decompose_forecast_completed(observation, cand_score.completed, fcs)
        real_b, fc_b = _decompose_forecast_completed(observation, b1_score.completed, fcs)
        out.notes.append(f"sc{i}:real_c={list(real_c)};fc_c={list(fc_c)};real_b={list(real_b)};fc_b={list(fc_b)}")

    out.pairs = pairs
    valid_deltas = [p.delta for p in pairs if p.valid_for_comparison]
    if not valid_deltas or len(valid_deltas) != len(pairs):
        out.notes.append("fail_closed_invalid_scenario_pair")
        return out
    mean_d = sum(valid_deltas) / len(valid_deltas)
    out.mean_delta = mean_d
    out.min_delta = min(valid_deltas)
    # Hoeffding LCB under independent bounded samples in [-DELTA_BOUND, DELTA_BOUND].
    # This is a bound under the forecast model — never a misspecification guarantee.
    n = len(valid_deltas)
    radius = DELTA_BOUND * sqrt(max(0.0, (1.0 / (2.0 * n)) * _log(2.0 / alpha)))
    out.hoeffding_lcb = mean_d - radius
    out.notes.append(f"hoeffding_alpha={alpha}")
    out.notes.append(f"delta_bound={DELTA_BOUND}")
    return out


def _log(x: float) -> float:
    from math import log

    return log(x)


def paired_evaluate_epoch(
    instance: Instance,
    observation: Observation,
    *,
    horizon: float,
    scenario_forecasts: list[list[ForecastCustomer]],
    alns_iterations: int = 10,
    alns_time: float = 0.25,
    seed: int = 0,
    energy: NominalLinearEnergy | None = None,
    max_replan_interval: float = 5.0,
    max_events: int = 200,
    alpha: float = 0.1,
) -> tuple[Decision, list[PairedCandidateReport]]:
    """Return executable B1 decision and paired reports for all distinct candidates."""
    model = energy or NominalLinearEnergy()
    b1 = build_b1_decision(
        instance,
        observation,
        horizon=horizon,
        alns_iterations=alns_iterations,
        alns_time=alns_time,
        seed=seed,
        energy=model,
    )
    candidates, _diag = generate_counterfactual_actions(
        instance,
        observation,
        horizon=horizon,
        energy=model,
        alns_iterations=alns_iterations,
        alns_time=max(0.05, alns_time * 0.5),
        seed=seed,
        include_solver_baselines=True,
        include_b1=True,
    )
    # Ensure B1 key is present exactly once as reference name.
    b1_key = FirstActionKey.from_decision(b1)
    reports: list[PairedCandidateReport] = []
    seen = {b1_key}
    reports.append(
        evaluate_paired_candidate(
            instance,
            observation,
            "b1",
            b1,
            b1,
            scenario_forecasts,
            horizon=horizon,
            max_replan_interval=max_replan_interval,
            max_events=max_events,
            energy=model,
            alpha=alpha,
        )
    )
    for name, cand in candidates:
        key = FirstActionKey.from_decision(cand)
        if key in seen:
            continue
        seen.add(key)
        reports.append(
            evaluate_paired_candidate(
                instance,
                observation,
                name,
                cand,
                b1,
                scenario_forecasts,
                horizon=horizon,
                max_replan_interval=max_replan_interval,
                max_events=max_events,
                energy=model,
                alpha=alpha,
            )
        )
    return b1, reports
