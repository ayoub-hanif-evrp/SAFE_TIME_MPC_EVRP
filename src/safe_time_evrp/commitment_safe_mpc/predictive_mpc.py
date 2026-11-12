"""Minimal commitment-safe predictive MPC (Phase 3D).

ALNS / insertion generate candidate routes. This controller selects among
validated first decisions using information-safe forecast scenarios and **causal
closed-loop scenario rollouts** (B1-validated recourse). Not claimed novel vs
standard stochastic MPC until pilot evidence says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, visible_forecast
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value


@dataclass
class PredictiveMpcProfile:
    decisions: int = 0
    scenarios_evaluated: int = 0
    validation_seconds: float = 0.0
    fallbacks: int = 0
    candidates_rejected_invalid: int = 0
    causal_rollouts: int = 0
    notes: list[str] = field(default_factory=list)


class CommitmentSafePredictiveMpc:
    """Event-triggered predictive MPC with validated fallback and causal rollouts."""

    def __init__(
        self,
        instance: Instance,
        horizon: float,
        *,
        forecast: ArrivalForecast | None = None,
        n_scenarios: int = 2,
        alns_iterations: int = 20,
        time_limit_seconds: float = 0.25,
        seed: int = 0,
        energy: NominalLinearEnergy | None = None,
        allocation: str = "uniform",
        max_replan_interval: float = 5.0,
        rollout_max_events: int = 400,
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
        self._alns = ReactiveAlnsMpc(
            instance,
            horizon,
            energy=self.energy,
            iterations=alns_iterations,
            time_limit_seconds=max(0.05, time_limit_seconds * 0.45),
            seed=seed,
        )
        self._insertion = EventTriggeredMPC(instance, horizon, self.energy)
        self._verified: dict[str, list[Visit]] | None = None
        self.profile = PredictiveMpcProfile()
        self.last_validation_status = "UNKNOWN"

    def _scenario_forecasts(self, observation: Observation) -> list[list]:
        if self.forecast is None:
            return []
        out = []
        for s_idx in range(self.n_scenarios):
            out.append(visible_forecast(observation, self.forecast, self.horizon, scenario_index=s_idx))
        return out

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        public = snapshot.instance
        notes = [
            "commitment_safe_predictive_mpc",
            f"allocation={self.allocation}",
            "causal_rollouts=1",
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

        raw_alns = self._alns.decide(observation, trigger)
        raw_ins = self._insertion.decide(observation, trigger)
        candidates: list[tuple[str, Decision]] = [("alns", raw_alns), ("insertion", raw_ins)]
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
            candidates.append(("incumbent", incumb))

        scenario_fcs = self._scenario_forecasts(observation)
        # Paired CRN: same scenario list order for every candidate (already index-ordered).
        if self.allocation == "uniform":
            pass

        scored: list[tuple[float, str, Decision, list[str]]] = []
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
                report2 = validate_continuation(public, observation, cand.routes, energy=self.energy)
                this_val += report2.seconds
                if not report2.ok:
                    self.profile.candidates_rejected_invalid += 1
                    continue
                cand = Decision(
                    time=cand.time,
                    routes=cand.routes,
                    accepted=list(observation.accepted),
                    newly_accepted=[],
                    rejected=list(cand.rejected) + list(cand.newly_accepted),
                    deferred=list(cand.deferred),
                    fallback_used=True,
                    no_feasible_continuation=False,
                    horizon_extended=cand.horizon_extended,
                    planned_service=list(cand.planned_service),
                    total_distance=cand.total_distance,
                    total_charge_time=cand.total_charge_time,
                    optimize_seconds=cand.optimize_seconds,
                    trigger=trigger,
                    locked_destinations=dict(cand.locked_destinations),
                    notes=list(cand.notes) + ["stripped_unvalidated_accepts"],
                )
                served = list(report2.served)
            else:
                served = list(report.served)

            if perf_counter() - started > self.time_limit_seconds:
                notes.append("deadline_before_causal_rollout")
                value = 100.0 * len(served)
            else:
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
                value = mean_v
            scored.append((value, name, cand, served))

        if scored:
            scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            _best_v, best_name, best, served = scored[0]
            newly = [c for c in best.newly_accepted if c in served]
            self._verified = {vid: list(vs) for vid, vs in best.routes.items()}
            status = "CERTIFIED_FEASIBLE"
            notes.append(f"selected={best_name}")
            accepted = list(observation.accepted)
            for c in newly:
                if c not in accepted:
                    accepted.append(c)
            routes = best.routes
            rejected = [c for c in best.rejected if c not in newly]
            deferred = list(best.deferred)
            fallback = bool(best.fallback_used)
            no_cont = False
        elif prev_ok and self._verified is not None:
            routes = {vid: list(vs) for vid, vs in self._verified.items()}
            newly = []
            accepted = list(observation.accepted)
            rejected = []
            deferred = []
            status = "CERTIFIED_FEASIBLE"
            fallback = True
            no_cont = False
            self.profile.fallbacks += 1
            notes.append("fallback_previous_witness")
        else:
            routes = {v.id: [] for v in observation.vehicles}
            newly = []
            accepted = list(observation.accepted)
            rejected = []
            deferred = []
            status = "UNKNOWN"
            fallback = True
            no_cont = True
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
                    "deadline_overrun": elapsed > self.time_limit_seconds,
                    "allocation": self.allocation,
                },
            },
        )
