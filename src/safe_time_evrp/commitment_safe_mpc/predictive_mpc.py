"""Minimal commitment-safe predictive MPC (Phase 3D).

ALNS / insertion generate candidate routes. This controller selects among
validated first decisions using information-safe forecast scenarios and B1
continuation validation. Not claimed novel vs OCBA / standard stochastic MPC
until pilot evidence says so.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc3c.forecast import (
    ArrivalForecast,
    ForecastCustomer,
    augment_instance_for_planning,
    visible_forecast,
)


@dataclass
class PredictiveMpcProfile:
    decisions: int = 0
    scenarios_evaluated: int = 0
    validation_seconds: float = 0.0
    fallbacks: int = 0
    candidates_rejected_invalid: int = 0
    notes: list[str] = field(default_factory=list)


def _forecast_lookahead_value(
    public: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    forecasts: list[ForecastCustomer],
    energy: NominalLinearEnergy,
) -> float:
    """Heuristic closed-loop proxy: how many forecast nodes remain insertable after commitments."""
    if not forecasts:
        return 0.0
    aug = augment_instance_for_planning(public, forecasts)
    # Score: +10 per forecast customer for which a single-vehicle append is feasible after routes.
    value = 0.0
    for vid, visits in routes.items():
        vview = next(v for v in observation.vehicles if v.id == vid)
        base = evaluate_route(aug, vview.anchor, visits, energy)
        if not base.feasible:
            continue
        for fc in forecasts:
            trial = list(visits) + [Visit(fc.customer_id, "service")]
            res = evaluate_route(aug, vview.anchor, trial, energy)
            if res.feasible and fc.customer_id in res.served:
                value += 10.0 - 0.1 * (res.distance - base.distance)
    return value


class CommitmentSafePredictiveMpc:
    """Event-triggered predictive MPC with validated fallback.

    Interface matches B0/B1/M1: ``decide(observation, trigger) -> Decision``.
    """

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
    ) -> None:
        self._full = instance
        self.horizon = horizon
        self.forecast = forecast
        self.n_scenarios = max(1, n_scenarios)
        self.energy = energy or NominalLinearEnergy()
        self.time_limit_seconds = time_limit_seconds
        self.allocation = allocation
        self._alns = ReactiveAlnsMpc(
            instance,
            horizon,
            energy=self.energy,
            iterations=alns_iterations,
            time_limit_seconds=max(0.05, time_limit_seconds * 0.6),
            seed=seed,
        )
        self._insertion = EventTriggeredMPC(instance, horizon, self.energy)
        self._verified: dict[str, list[Visit]] | None = None
        self.profile = PredictiveMpcProfile()
        self.last_validation_status = "UNKNOWN"

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        public = snapshot.instance
        notes = ["commitment_safe_predictive_mpc", f"allocation={self.allocation}"]
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

        # Candidate generators: ALNS + insertion (physically executable proposals).
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

        scored: list[tuple[float, str, Decision, list[str]]] = []
        scenario_budget = self.n_scenarios
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
                # Drop new accepts; try commitments-only validation.
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
                nom_dist = report2.distance
            else:
                served = list(report.served)
                nom_dist = report.distance

            value = 100.0 * len(served) - nom_dist
            if self.forecast is not None:
                # Uniform / equal scenario indices (deterministic; order-stable).
                indices = list(range(scenario_budget))
                if self.allocation == "paired_crn":
                    indices = list(range(scenario_budget))  # same set for every candidate
                for s_idx in indices:
                    if perf_counter() - started > self.time_limit_seconds:
                        notes.append("deadline_during_forecast_eval")
                        break
                    fcs = visible_forecast(observation, self.forecast, self.horizon, scenario_index=s_idx)
                    self.profile.scenarios_evaluated += 1
                    value += _forecast_lookahead_value(public, observation, cand.routes, fcs, self.energy)
            scored.append((value, name, cand, served))

        if scored:
            # Lexicographic: value, then name (order-stable among ties).
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
                    "n_candidates_scored": len(scored),
                    "deadline_overrun": elapsed > self.time_limit_seconds,
                    "allocation": self.allocation,
                },
            },
        )
