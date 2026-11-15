"""Baseline-anchored predictive CC-E-MPC.

Incumbent = greedy-nominal CC-E (strong exploratory reference). Forecast-based
overrides are selected only when CRN paired improvement over the incumbent is
credible. Hard obligation feasibility is never relaxed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.certificate_store import CertificateStore
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    FiniteDemandModel,
    expected_remaining_given_public,
    sample_finite_demand_scenarios,
)
from safe_time_evrp.mpc3c.forecast import ArrivalForecast
from safe_time_evrp.mpc_central.cce_mpc import CCEMpcProfile, CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.counterfactual_actions import (
    FirstActionKey,
    generate_counterfactual_actions,
    sanitize_newly_accepted,
    sanitize_rejects,
    sanitize_routes,
)
from safe_time_evrp.mpc_central.flexibility_features import prioritize_candidates_for_rollout
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value, is_quiescent

# Train/dev-selected margin (not tuned on final held-out eval).
DEFAULT_IMPROVEMENT_MARGIN = 0.35
DEFAULT_CONFIRM_SCENARIOS = 1
DELTA_BOUND = 50.0  # for Hoeffding-style noise accounting on bounded deltas


@dataclass
class BAPProfile:
    decisions: int = 0
    incumbent_kept: int = 0
    overrides: int = 0
    fallbacks: int = 0
    deadline_overruns: int = 0
    scenarios_evaluated: int = 0
    scoring_seconds: float = 0.0
    last_mean_delta: float | None = None
    notes: list[str] = field(default_factory=list)


class BaselineAnchoredPredictiveCCE:
    """Greedy-nominal incumbent with optional finite-demand predictive override."""

    def __init__(
        self,
        instance: Instance,
        horizon: float,
        *,
        forecast: ArrivalForecast | None = None,
        finite_model: FiniteDemandModel | None = None,
        n_scenarios: int = 2,
        alns_iterations: int = 10,
        time_limit_seconds: float = 0.35,
        seed: int = 0,
        energy: NominalLinearEnergy | None = None,
        max_replan_interval: float = 5.0,
        rollout_max_events: int = 120,
        improvement_margin: float = DEFAULT_IMPROVEMENT_MARGIN,
        max_rollout_candidates: int = 5,
        use_finite_demand: bool = True,
    ) -> None:
        self._full = instance
        self.horizon = horizon
        self.forecast = forecast
        self.finite_model = finite_model
        self.n_scenarios = max(1, n_scenarios)
        self.energy = energy or NominalLinearEnergy()
        self.time_limit_seconds = time_limit_seconds
        self.seed = seed
        self.alns_iterations = alns_iterations
        self.max_replan_interval = max_replan_interval
        self.rollout_max_events = rollout_max_events
        self.improvement_margin = improvement_margin
        self.max_rollout_candidates = max_rollout_candidates
        self.use_finite_demand = use_finite_demand
        # Unchanged greedy-nominal CC-E as persistent incumbent generator.
        self._incumbent = CertificateCarryingEconomicMpc(
            instance,
            horizon,
            forecast=forecast,
            n_scenarios=n_scenarios,
            alns_iterations=alns_iterations,
            time_limit_seconds=max(0.05, time_limit_seconds * 0.45),
            seed=seed,
            energy=self.energy,
            use_forecast=False,
            use_persistent_certificate=True,
            scoring_mode="greedy_nominal",
            max_replan_interval=max_replan_interval,
            rollout_max_events=rollout_max_events,
        )
        self.store = CertificateStore()
        self._last_certified_routes: dict[str, list[Visit]] | None = None
        self.profile = BAPProfile()
        # Expose CCE-like fields for eval summarizers.
        self.last_validation_status = "UNKNOWN"
        self.last_audit: dict = {}
        self.cce_profile = CCEMpcProfile()

    def _sanitize(self, observation: Observation, decision: Decision, *, trigger: str) -> Decision:
        routes = sanitize_routes(observation, decision.routes)
        newly = sanitize_newly_accepted(observation, list(decision.newly_accepted))
        rejected = sanitize_rejects(observation, [c for c in decision.rejected if c not in newly])
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
            deferred=list(decision.deferred),
            fallback_used=decision.fallback_used,
            no_feasible_continuation=decision.no_feasible_continuation,
            horizon_extended=decision.horizon_extended,
            planned_service=sorted({v.node_id for vs in routes.values() for v in vs if v.purpose == "service"}),
            total_distance=decision.total_distance,
            total_charge_time=decision.total_charge_time,
            optimize_seconds=decision.optimize_seconds,
            trigger=trigger,
            locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
            notes=list(decision.notes),
        )

    def _scenarios(self, observation: Observation) -> list[list]:
        if self.use_finite_demand and self.finite_model is not None:
            return sample_finite_demand_scenarios(
                self.finite_model,
                observation,
                self._full,
                horizon=self.horizon,
                n_scenarios=self.n_scenarios,
                seed=self.seed,
            )
        # Empty-future causal scenarios if no finite model.
        return [[] for _ in range(self.n_scenarios)]

    def _emit(
        self,
        observation: Observation,
        *,
        routes: dict[str, list[Visit]],
        newly: list[str],
        rejected: list[str],
        deferred: list[str],
        notes: list[str],
        status: str,
        fallback: bool,
        no_cont: bool,
        started: float,
        trigger: str,
        served: list[str] | None = None,
    ) -> Decision:
        public = make_public_snapshot(self._full, observation, self.horizon).instance
        report = validate_continuation(
            public,
            observation,
            routes,
            energy=self.energy,
            require_new=frozenset(newly),
        )
        if not report.ok:
            status = "UNKNOWN"
            notes = list(notes) + ["emit_validation_failed"] + list(report.reasons[:2])
            routes = {v.id: [] for v in observation.vehicles}
            newly = []
            no_cont = True
            fallback = True
            served = []
        else:
            served = list(report.served) if served is None else [c for c in newly if c in report.served]
            newly = sanitize_newly_accepted(observation, [c for c in newly if c in report.served])
            if status.startswith("CERTIFIED"):
                accepted_set = frozenset(list(observation.accepted) + newly)
                self.store.publish(routes, observation, list(report.served), accepted=accepted_set)
                self._last_certified_routes = {vid: list(vs) for vid, vs in routes.items()}
        self.last_validation_status = status
        elapsed = perf_counter() - started
        if elapsed > self.time_limit_seconds:
            self.profile.deadline_overruns += 1
            notes = list(notes) + ["deadline_overrun"]
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
            deferred=deferred,
            fallback_used=fallback,
            no_feasible_continuation=no_cont,
            horizon_extended=False,
            planned_service=sorted({v.node_id for vs in routes.values() for v in vs if v.purpose == "service"}),
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=elapsed,
            trigger=trigger,
            locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
            notes=notes,
            audit={"bap_cce": self.last_audit},
        )

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        notes = [
            "baseline_anchored_predictive_cce",
            "incumbent=greedy_nominal_cce",
            f"use_finite_demand={int(self.use_finite_demand)}",
            f"improvement_margin={self.improvement_margin}",
            "quiescent" if is_quiescent(observation) else "busy_epoch",
            "hard_commitment_feasibility=1",
        ]
        # 1) Always compute feasible greedy-nominal incumbent first (anytime fallback).
        incumb_raw = self._incumbent.decide(observation, trigger)
        incumbent = self._sanitize(observation, incumb_raw, trigger="greedy_nominal_incumbent")
        public = make_public_snapshot(self._full, observation, self.horizon).instance
        inc_rep = validate_continuation(
            public,
            observation,
            incumbent.routes,
            energy=self.energy,
            require_new=frozenset(incumbent.newly_accepted),
        )
        if not inc_rep.ok:
            # Soften new accepts; keep routes if possible.
            incumbent = self._sanitize(
                observation,
                Decision(
                    time=observation.time,
                    routes=incumbent.routes,
                    accepted=list(observation.accepted),
                    newly_accepted=[],
                    rejected=list(incumbent.rejected),
                    deferred=list(incumbent.deferred),
                    fallback_used=True,
                    no_feasible_continuation=False,
                    horizon_extended=False,
                    planned_service=[],
                    total_distance=0.0,
                    total_charge_time=0.0,
                    optimize_seconds=0.0,
                    trigger=trigger,
                    locked_destinations={},
                    notes=["incumbent_stripped_new_accepts"],
                ),
                trigger="greedy_nominal_incumbent",
            )
            inc_rep = validate_continuation(public, observation, incumbent.routes, energy=self.energy)
        if not inc_rep.ok:
            self.profile.fallbacks += 1
            self.profile.decisions += 1
            notes.append("incumbent_infeasible_empty_fallback")
            return self._emit(
                observation,
                routes={v.id: [] for v in observation.vehicles},
                newly=[],
                rejected=[],
                deferred=[],
                notes=notes,
                status="UNKNOWN",
                fallback=True,
                no_cont=True,
                started=started,
                trigger=trigger,
            )

        remaining_meta = (
            expected_remaining_given_public(self.finite_model, self._full, observation, horizon=self.horizon)
            if self.finite_model is not None
            else {"expected_remaining": 0.0}
        )
        expected_rem = float(remaining_meta.get("expected_remaining", 0.0))
        notes.append(f"expected_remaining={expected_rem:.3f}")

        # Budget check: if little time left, execute incumbent.
        if perf_counter() - started > self.time_limit_seconds * 0.85:
            self.profile.incumbent_kept += 1
            self.profile.decisions += 1
            notes.append("anytime_incumbent_deadline")
            return self._emit(
                observation,
                routes=incumbent.routes,
                newly=list(incumbent.newly_accepted),
                rejected=list(incumbent.rejected),
                deferred=list(incumbent.deferred),
                notes=notes,
                status="CERTIFIED_FEASIBLE",
                fallback=False,
                no_cont=False,
                started=started,
                trigger=trigger,
                served=list(inc_rep.served),
            )

        # 2) Generate alternatives; screen with flexibility features.
        t_gen = perf_counter()
        candidates, _diag = generate_counterfactual_actions(
            self._full,
            observation,
            horizon=self.horizon,
            energy=self.energy,
            alns_iterations=self.alns_iterations,
            alns_time=max(0.05, self.time_limit_seconds * 0.25),
            seed=self.seed,
            include_solver_baselines=True,
            include_b1=True,
        )
        named = [("greedy_nominal_incumbent", incumbent)] + [
            (n, self._sanitize(observation, c, trigger=n))
            for n, c in candidates
            if FirstActionKey.from_decision(c) != FirstActionKey.from_decision(incumbent)
        ]
        named = prioritize_candidates_for_rollout(
            named,
            observation,
            expected_remaining=expected_rem,
            max_keep=self.max_rollout_candidates,
        )
        notes.append(f"n_rollout_candidates={len(named)}")

        # 3) Shared finite-demand scenarios (CRN across candidates).
        scenarios = self._scenarios(observation)
        notes.append(f"n_scenarios={len(scenarios)}")
        notes.append(f"n_fc_sc0={len(scenarios[0]) if scenarios else 0}")

        # 4) Score incumbent + alternatives on the same scenarios (causal objective).
        t_score = perf_counter()
        scored: list[tuple[float, str, Decision, list[str]]] = []
        for name, cand in named:
            if perf_counter() - started > self.time_limit_seconds:
                notes.append("cooperative_deadline_hit_during_scoring")
                break
            rep = validate_continuation(
                public,
                observation,
                cand.routes,
                energy=self.energy,
                require_new=frozenset(cand.newly_accepted),
            )
            if not rep.ok:
                continue
            mean_v, scores = expected_rollout_value(
                self._full,
                observation,
                cand,
                scenarios,
                horizon=self.horizon,
                scoring_mode="causal",
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
            )
            self.profile.scenarios_evaluated += len(scores)
            if mean_v <= -1e8:
                continue
            scored.append((mean_v, name, cand, list(rep.served)))
        self.profile.scoring_seconds += perf_counter() - t_score
        self.profile.decisions += 1

        if not scored:
            self.profile.incumbent_kept += 1
            notes.append("no_scored_candidates_keep_incumbent")
            return self._emit(
                observation,
                routes=incumbent.routes,
                newly=list(incumbent.newly_accepted),
                rejected=list(incumbent.rejected),
                deferred=list(incumbent.deferred),
                notes=notes,
                status="CERTIFIED_FEASIBLE",
                fallback=False,
                no_cont=False,
                started=started,
                trigger=trigger,
                served=list(inc_rep.served),
            )

        # Identify incumbent value under causal scenarios.
        inc_key = FirstActionKey.from_decision(incumbent)
        inc_val = None
        for v, name, cand, _s in scored:
            if name == "greedy_nominal_incumbent" or FirstActionKey.from_decision(cand) == inc_key:
                inc_val = v
                break
        if inc_val is None:
            # Score incumbent explicitly.
            inc_val, _ = expected_rollout_value(
                self._full,
                observation,
                incumbent,
                scenarios,
                horizon=self.horizon,
                scoring_mode="causal",
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
            )

        scored.sort(key=lambda x: x[0], reverse=True)
        best_v, best_name, best, served = scored[0]
        delta = best_v - float(inc_val)
        self.profile.last_mean_delta = delta
        notes.append(f"best={best_name}")
        notes.append(f"delta_vs_incumbent={delta:.4f}")

        # Noise margin: require delta > margin (train-selected). Optional Hoeffding radius.
        n_sc = max(1, len(scenarios))
        radius = DELTA_BOUND * sqrt(max(0.0, (1.0 / (2.0 * n_sc)) * 0.5))  # rough α≈0.6 honesty term
        # Prefer margin rule; radius recorded only.
        notes.append(f"noise_radius~{radius:.3f}")
        override = (
            best_name != "greedy_nominal_incumbent"
            and FirstActionKey.from_decision(best) != inc_key
            and delta > self.improvement_margin
        )
        self.last_audit = {
            "incumbent_value": inc_val,
            "best_value": best_v,
            "delta": delta,
            "override": override,
            "expected_remaining": expected_rem,
            "candidate_gen_seconds": perf_counter() - t_gen,
        }

        if not override:
            self.profile.incumbent_kept += 1
            notes.append("keep_incumbent")
            chosen, chosen_newly, chosen_served = incumbent, list(incumbent.newly_accepted), list(inc_rep.served)
            rejected, deferred = list(incumbent.rejected), list(incumbent.deferred)
        else:
            self.profile.overrides += 1
            notes.append("override_incumbent")
            chosen, chosen_newly, chosen_served = best, list(best.newly_accepted), served
            rejected, deferred = list(best.rejected), list(best.deferred)

        return self._emit(
            observation,
            routes=chosen.routes,
            newly=sanitize_newly_accepted(observation, [c for c in chosen_newly if c in chosen_served]),
            rejected=rejected,
            deferred=deferred,
            notes=notes,
            status="CERTIFIED_FEASIBLE",
            fallback=False,
            no_cont=False,
            started=started,
            trigger=trigger,
            served=chosen_served,
        )
