"""Commitment-preserving counterfactual predictive MPC.

Generates distinct safe first actions, scores them with causal scenario rollouts,
and executes only the chosen first plant action. ALNS is a route subroutine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, visible_forecast
from safe_time_evrp.mpc_central.counterfactual_actions import (
    CounterfactualDiagnostics,
    FirstActionKey,
    generate_counterfactual_actions,
    sanitize_newly_accepted,
    sanitize_rejects,
    sanitize_routes,
)
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value, is_quiescent


@dataclass
class PredictiveMpcProfile:
    decisions: int = 0
    scenarios_evaluated: int = 0
    validation_seconds: float = 0.0
    fallbacks: int = 0
    candidates_rejected_invalid: int = 0
    causal_rollouts: int = 0
    candidate_gen_seconds: float = 0.0
    scoring_seconds: float = 0.0
    last_diagnostics: CounterfactualDiagnostics | None = None
    notes: list[str] = field(default_factory=list)


class CommitmentSafePredictiveMpc:
    """Counterfactual commitment-safe predictive MPC."""

    def __init__(
        self,
        instance: Instance,
        horizon: float,
        *,
        forecast: ArrivalForecast | None = None,
        n_scenarios: int = 2,
        alns_iterations: int = 12,
        time_limit_seconds: float = 0.4,
        seed: int = 0,
        energy: NominalLinearEnergy | None = None,
        allocation: str = "uniform",
        max_replan_interval: float = 5.0,
        rollout_max_events: int = 300,
        use_counterfactuals: bool = True,
        use_forecast: bool = True,
    ) -> None:
        self._full = instance
        self.horizon = horizon
        self.forecast = forecast
        self.n_scenarios = max(1, n_scenarios)
        self.energy = energy or NominalLinearEnergy()
        self.time_limit_seconds = time_limit_seconds
        self.allocation = allocation
        self.max_replan_interval = max_replan_interval
        self.rollout_max_events = rollout_max_events
        self.use_counterfactuals = use_counterfactuals
        self.use_forecast = use_forecast
        self.alns_iterations = alns_iterations
        self.seed = seed
        self._verified: dict[str, list[Visit]] | None = None
        self.profile = PredictiveMpcProfile()
        self.last_validation_status = "UNKNOWN"

    def _scenario_forecasts(self, observation: Observation) -> list[list]:
        if not self.use_forecast or self.forecast is None:
            return []
        return [
            visible_forecast(observation, self.forecast, self.horizon, scenario_index=s_idx)
            for s_idx in range(self.n_scenarios)
        ]

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        public = snapshot.instance
        notes = [
            "commitment_safe_predictive_mpc",
            f"allocation={self.allocation}",
            "causal_rollouts=1",
            "counterfactual_actions=1" if self.use_counterfactuals else "solver_only_candidates",
            "quiescent" if is_quiescent(observation) else "busy_epoch",
        ]
        this_val = 0.0

        prev_ok = False
        if self._verified is not None:
            prev = validate_continuation(public, observation, self._verified, energy=self.energy)
            this_val += prev.seconds
            if prev.ok:
                prev_ok = True
            else:
                self._verified = None
                notes.append("previous_witness_invalidated")

        t_gen = perf_counter()
        if self.use_counterfactuals:
            candidates, diag = generate_counterfactual_actions(
                self._full,
                observation,
                horizon=self.horizon,
                energy=self.energy,
                alns_iterations=self.alns_iterations,
                alns_time=max(0.05, self.time_limit_seconds * 0.25),
                seed=self.seed,
                include_solver_baselines=True,
            )
        else:
            from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
            from safe_time_evrp.controllers.mpc import EventTriggeredMPC

            alns = ReactiveAlnsMpc(
                self._full,
                self.horizon,
                energy=self.energy,
                iterations=self.alns_iterations,
                time_limit_seconds=max(0.05, self.time_limit_seconds * 0.25),
                seed=self.seed,
            )
            ins = EventTriggeredMPC(self._full, self.horizon, self.energy)
            candidates = [("alns", alns.decide(observation, trigger)), ("insertion", ins.decide(observation, trigger))]
            diag = CounterfactualDiagnostics(
                raw_candidates=2, distinct_first_actions=len(candidates), valid_commitment_safe=len(candidates)
            )
        self.profile.candidate_gen_seconds += perf_counter() - t_gen
        self.profile.last_diagnostics = diag
        notes.append(f"n_valid_actions={len(candidates)}")

        if prev_ok and self._verified is not None:
            incumb = Decision(
                time=observation.time,
                routes={vid: list(vs) for vid, vs in self._verified.items()},
                accepted=list(observation.accepted),
                newly_accepted=[],
                rejected=[],
                deferred=[],
                fallback_used=False,
                no_feasible_continuation=False,
                horizon_extended=False,
                planned_service=[],
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=0.0,
                trigger=trigger,
                locked_destinations={},
                notes=["incumbent_witness"],
            )
            key = FirstActionKey.from_decision(incumb)
            if all(FirstActionKey.from_decision(c) != key for _, c in candidates):
                report = validate_continuation(public, observation, incumb.routes, energy=self.energy)
                this_val += report.seconds
                if report.ok:
                    candidates.append(("incumbent", incumb))

        scenario_fcs = self._scenario_forecasts(observation)
        scored: list[tuple[float, str, Decision, list[str]]] = []
        t_score = perf_counter()
        for name, cand in candidates:
            if perf_counter() - started > self.time_limit_seconds:
                notes.append("cooperative_deadline_hit_during_scoring")
                break
            report = validate_continuation(
                public,
                observation,
                cand.routes,
                energy=self.energy,
                require_new=frozenset(cand.newly_accepted),
            )
            this_val += report.seconds
            if not report.ok:
                self.profile.candidates_rejected_invalid += 1
                continue
            served = list(report.served)
            mean_v, scores = expected_rollout_value(
                self._full,
                observation,
                cand,
                scenario_fcs,
                horizon=self.horizon,
                max_scenarios=self.n_scenarios,
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
            )
            self.profile.scenarios_evaluated += len(scores)
            self.profile.causal_rollouts += len(scores)
            scored.append((mean_v, name, cand, served))
        self.profile.scoring_seconds += perf_counter() - t_score

        if scored:
            # Tie-break: higher value, then more new accepts, then more service first-legs,
            # then prefer non-wait names — never let "wait_idle" beat an equal-valued serve.
            def _rank(item: tuple[float, str, Decision, list[str]]):
                value, name, cand, _served = item
                key = FirstActionKey.from_decision(cand)
                n_service = sum(1 for leg in key.first_legs if leg[2] == "service")
                not_wait = 0 if name.startswith("wait") or name == "wait_idle" else 1
                return (value, len(key.newly_accepted), n_service, not_wait, name)

            scored.sort(key=_rank, reverse=True)
            _best_v, best_name, best, served = scored[0]
            newly = sanitize_newly_accepted(
                observation, [c for c in best.newly_accepted if c in served and c not in observation.completed]
            )
            routes = sanitize_routes(observation, best.routes)
            self._verified = {vid: list(vs) for vid, vs in routes.items()}
            status = "CERTIFIED_FEASIBLE"
            notes.append(f"selected={best_name}")
            diag.selected_key = FirstActionKey.from_decision(best)
            accepted = list(observation.accepted)
            for c in newly:
                if c not in accepted:
                    accepted.append(c)
            rejected = sanitize_rejects(observation, [c for c in best.rejected if c not in newly])
            deferred = list(best.deferred)
            fallback = bool(best.fallback_used)
            no_cont = False
        elif prev_ok and self._verified is not None:
            routes = sanitize_routes(observation, {vid: list(vs) for vid, vs in self._verified.items()})
            newly, accepted, rejected, deferred = [], list(observation.accepted), [], []
            status = "CERTIFIED_FEASIBLE"
            fallback, no_cont = True, False
            self.profile.fallbacks += 1
            notes.append("fallback_previous_witness")
        else:
            routes = {v.id: [] for v in observation.vehicles}
            newly, accepted, rejected, deferred = [], list(observation.accepted), [], []
            status = "UNKNOWN"
            fallback, no_cont = True, True
            self.profile.fallbacks += 1
            notes.append("status=UNKNOWN")

        self.last_validation_status = status
        self.profile.decisions += 1
        self.profile.validation_seconds += this_val
        elapsed = perf_counter() - started
        planned = [v.node_id for vs in routes.values() for v in vs if v.purpose == "service"]
        return Decision(
            time=observation.time,
            routes=routes,
            accepted=accepted,
            newly_accepted=newly,
            rejected=rejected,
            deferred=deferred,
            fallback_used=fallback,
            no_feasible_continuation=no_cont,
            horizon_extended=False,
            planned_service=sorted(set(planned)),
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=elapsed,
            trigger=trigger,
            locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
            notes=notes,
            audit={
                "validation_status": status,
                "validation_seconds_this_decision": this_val,
                "predictive_mpc": {
                    "scenarios_evaluated": self.profile.scenarios_evaluated,
                    "causal_rollouts": self.profile.causal_rollouts,
                    "n_candidates_scored": len(scored),
                    "n_valid_actions": diag.valid_commitment_safe,
                    "n_distinct_first_actions": diag.distinct_first_actions,
                    "deadline_overrun": elapsed > self.time_limit_seconds,
                    "allocation": self.allocation,
                    "use_forecast": self.use_forecast,
                    "candidate_gen_seconds": self.profile.candidate_gen_seconds,
                    "scoring_seconds": self.profile.scoring_seconds,
                },
            },
        )
