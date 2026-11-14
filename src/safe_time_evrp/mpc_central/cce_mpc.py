"""Certificate-Carrying Economic Model Predictive Control (CC-E-MPC).

Hard constraint: every accepted / newly accepted obligation retains a verified
nominal continuation certificate.

Soft objective: among commitment-feasible first actions, maximize expected
economic value under shared forecast scenarios and causal B1-validated recourse.

NOT a safety constraint: reward below B1 in an individual forecast scenario.

Fallback: if optimization fails, times out without a valid scored candidate, or
invalidates the new plan, execute the advanced persistent certificate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.certificate_store import CertificateStore
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, ForecastCustomer, visible_forecast
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
class CCEMpcProfile:
    decisions: int = 0
    scenarios_evaluated: int = 0
    causal_rollouts: int = 0
    validation_seconds: float = 0.0
    candidate_gen_seconds: float = 0.0
    scoring_seconds: float = 0.0
    fallbacks: int = 0
    certificate_reuses: int = 0
    certificate_invalidations: int = 0
    certificate_publishes: int = 0
    deadline_overruns: int = 0
    selected_charge: int = 0
    selected_service: int = 0
    last_diagnostics: CounterfactualDiagnostics | None = None
    notes: list[str] = field(default_factory=list)


class CertificateCarryingEconomicMpc:
    """CC-E-MPC: persistent certificate + expected-value selection among feasible actions."""

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
        max_replan_interval: float = 5.0,
        rollout_max_events: int = 300,
        use_forecast: bool = True,
        use_persistent_certificate: bool = True,
        scenario_override: list[list[ForecastCustomer]] | None = None,
        first_leg_allowlist: frozenset[tuple[tuple[str, str, str], ...]] | None = None,
    ) -> None:
        self._full = instance
        self.horizon = horizon
        self.forecast = forecast
        self.n_scenarios = max(1, n_scenarios)
        self.energy = energy or NominalLinearEnergy()
        self.time_limit_seconds = time_limit_seconds
        self.seed = seed
        self.alns_iterations = alns_iterations
        self.max_replan_interval = max_replan_interval
        self.rollout_max_events = rollout_max_events
        self.use_forecast = use_forecast
        self.use_persistent_certificate = use_persistent_certificate
        self.scenario_override = scenario_override
        # Optional restricted first-action set (Case-A paper oracle). None = full generator.
        self.first_leg_allowlist = first_leg_allowlist
        self.store = CertificateStore()
        # Dual retention (same pattern as M1): store may invalidate on advance while
        # the last independently verified routes remain available for fallback attempts.
        self._last_certified_routes: dict[str, list[Visit]] | None = None
        self.profile = CCEMpcProfile()
        self.last_validation_status = "UNKNOWN"
        self.last_audit: dict = {}
        self.last_obligation_gap: list[str] = []

    def _scenario_forecasts(self, observation: Observation) -> list[list[ForecastCustomer]]:
        if self.scenario_override is not None:
            return list(self.scenario_override)
        if not self.use_forecast or self.forecast is None:
            return []
        return [
            visible_forecast(observation, self.forecast, self.horizon, scenario_index=s_idx)
            for s_idx in range(self.n_scenarios)
        ]

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
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        public = snapshot.instance
        routes = sanitize_routes(observation, routes)
        newly = sanitize_newly_accepted(observation, newly)
        rejected = sanitize_rejects(observation, [c for c in rejected if c not in newly])
        accepted = list(observation.accepted)
        for c in newly:
            if c not in accepted:
                accepted.append(c)
        accepted_set = frozenset(accepted)

        # Independent verify: CERTIFIED_FEASIBLE requires coverage of the full post-decision set.
        if status == "CERTIFIED_FEASIBLE":
            rep = validate_continuation(
                public,
                observation,
                routes,
                energy=self.energy,
                require_new=frozenset(newly),
            )
            if not rep.ok:
                status = "UNKNOWN"
                fallback = True
                no_cont = True
                notes.append("certified_claim_demoted_independent_verify_failed")
                notes.extend(rep.reasons[:3])
            else:
                served = list(rep.served)
                if self.use_persistent_certificate:
                    self.store.publish(
                        routes,
                        observation,
                        served,
                        accepted=accepted_set,
                    )
                    self.profile.certificate_publishes += 1
                self._last_certified_routes = {vid: list(vs) for vid, vs in routes.items()}

        pending = set(accepted) - set(observation.completed) - set(observation.in_service)
        if status != "CERTIFIED_FEASIBLE" and pending:
            # Do not silently pretend commitments are covered.
            notes.append(f"uncovered_accepted_obligations:{sorted(pending)}")
            self.last_obligation_gap = sorted(pending)
            no_cont = True
        else:
            self.last_obligation_gap = []

        planned = [v.node_id for vs in routes.values() for v in vs if v.purpose == "service"]
        elapsed = perf_counter() - started
        if elapsed > self.time_limit_seconds:
            self.profile.deadline_overruns += 1
            notes.append("deadline_overrun")
        key = FirstActionKey.from_decision(
            Decision(
                observation.time,
                routes,
                accepted,
                newly,
                rejected,
                deferred,
                fallback,
                no_cont,
                False,
                planned,
                0.0,
                0.0,
                elapsed,
                trigger,
                {},
                notes,
            )
        )
        if any(leg[2] == "charge" for leg in key.first_legs):
            self.profile.selected_charge += 1
        if any(leg[2] == "service" for leg in key.first_legs):
            self.profile.selected_service += 1
        self.last_validation_status = status
        self.last_audit = {
            "validation_status": status,
            "fallback": fallback,
            "certificate_version": None if self.store.current is None else self.store.current.version,
            "first_legs": [list(x) for x in key.first_legs],
            "newly_accepted": list(newly),
            "accepted_post_decision": sorted(accepted_set),
            "obligation_gap": list(self.last_obligation_gap),
            "independent_cert_ok": status == "CERTIFIED_FEASIBLE",
        }
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
            audit={"cce_mpc": self.last_audit},
        )

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        public = snapshot.instance
        notes = [
            "certificate_carrying_economic_mpc",
            f"use_forecast={int(self.use_forecast)}",
            f"persistent_certificate={int(self.use_persistent_certificate)}",
            "quiescent" if is_quiescent(observation) else "busy_epoch",
            "hard_commitment_feasibility=1",
            "no_scenario_regret_floor=1",
        ]
        this_val = 0.0

        prev_ok = False
        fallback_routes: dict[str, list[Visit]] | None = None
        if self.use_persistent_certificate:
            retained = self.store.advance_or_invalidate(observation)
            if retained is not None:
                rep = validate_continuation(public, observation, retained.routes, energy=self.energy)
                this_val += rep.seconds
                if rep.ok:
                    prev_ok = True
                    fallback_routes = {vid: list(vs) for vid, vs in retained.routes.items()}
                    self._last_certified_routes = {vid: list(vs) for vid, vs in retained.routes.items()}
                    self.profile.certificate_reuses += 1
                    notes.append("certificate_advanced_ok")
                else:
                    self.store.invalidate_count += 1
                    self.store.current = None
                    self.profile.certificate_invalidations += 1
                    notes.append("certificate_invalidated_on_recheck")
            elif self.store.current is None and self.store.invalidate_count:
                notes.append("certificate_absent_after_invalidation")
            # Secondary fallback: last independently verified routes (M1-style retention).
            if not prev_ok and self._last_certified_routes is not None:
                rep2 = validate_continuation(public, observation, self._last_certified_routes, energy=self.energy)
                this_val += rep2.seconds
                if rep2.ok:
                    prev_ok = True
                    fallback_routes = {vid: list(vs) for vid, vs in self._last_certified_routes.items()}
                    notes.append("fallback_last_certified_routes_revalidated")
                    self.profile.certificate_reuses += 1

        t_gen = perf_counter()
        candidates, diag = generate_counterfactual_actions(
            self._full,
            observation,
            horizon=self.horizon,
            energy=self.energy,
            alns_iterations=self.alns_iterations,
            alns_time=max(0.05, self.time_limit_seconds * 0.3),
            seed=self.seed,
            include_solver_baselines=True,
            include_b1=True,
        )
        self.profile.candidate_gen_seconds += perf_counter() - t_gen
        if self.first_leg_allowlist is not None:
            filtered = []
            for name, cand in candidates:
                legs = FirstActionKey.from_decision(cand).first_legs
                if legs in self.first_leg_allowlist:
                    filtered.append((name, cand))
            candidates = filtered
            notes.append(f"first_leg_allowlist_n={len(candidates)}")
        self.profile.last_diagnostics = diag
        notes.append(f"n_valid_actions={len(candidates)}")

        if prev_ok and fallback_routes is not None:
            incumb = Decision(
                time=observation.time,
                routes={vid: list(vs) for vid, vs in fallback_routes.items()},
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
                notes=["incumbent_certificate"],
            )
            key = FirstActionKey.from_decision(incumb)
            if all(FirstActionKey.from_decision(c) != key for _, c in candidates):
                candidates = list(candidates) + [("incumbent_certificate", incumb)]

        scenario_fcs = self._scenario_forecasts(observation)
        scored: list[tuple[float, str, Decision, list[str]]] = []
        t_score = perf_counter()
        for name, cand in candidates:
            if perf_counter() - started > self.time_limit_seconds:
                notes.append("cooperative_deadline_hit_during_scoring")
                break
            routes = sanitize_routes(observation, cand.routes)
            newly = sanitize_newly_accepted(observation, list(cand.newly_accepted))
            cand = Decision(
                time=observation.time,
                routes=routes,
                accepted=list(observation.accepted) + [c for c in newly if c not in observation.accepted],
                newly_accepted=newly,
                rejected=sanitize_rejects(observation, [c for c in cand.rejected if c not in newly]),
                deferred=list(cand.deferred),
                fallback_used=cand.fallback_used,
                no_feasible_continuation=False,
                horizon_extended=False,
                planned_service=list(cand.planned_service),
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=0.0,
                trigger=cand.trigger,
                locked_destinations=dict(cand.locked_destinations),
                notes=list(cand.notes),
            )
            report = validate_continuation(
                public,
                observation,
                cand.routes,
                energy=self.energy,
                require_new=frozenset(cand.newly_accepted),
            )
            this_val += report.seconds
            if not report.ok:
                continue
            mean_v, scores = expected_rollout_value(
                self._full,
                observation,
                cand,
                scenario_fcs,
                horizon=self.horizon,
                max_scenarios=self.n_scenarios if scenario_fcs else None,
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
            )
            self.profile.scenarios_evaluated += len(scores)
            self.profile.causal_rollouts += len(scores)
            if mean_v <= -1e8:
                continue
            scored.append((mean_v, name, cand, list(report.served)))
        self.profile.scoring_seconds += perf_counter() - t_score
        self.profile.validation_seconds += this_val
        self.profile.decisions += 1

        if scored:

            def _rank(item: tuple[float, str, Decision, list[str]]):
                value, name, cand, _served = item
                key = FirstActionKey.from_decision(cand)
                n_service = sum(1 for leg in key.first_legs if leg[2] == "service")
                n_charge = sum(1 for leg in key.first_legs if leg[2] == "charge")
                not_wait = 0 if name.startswith("wait") or name == "wait_idle" else 1
                # Expected value first; charge/service preference only breaks exact ties.
                return (value, n_charge, n_service, len(key.newly_accepted), not_wait, name)

            scored.sort(key=_rank, reverse=True)
            best_v, best_name, best, served = scored[0]
            notes.append(f"selected={best_name}")
            notes.append(f"expected_value={best_v:.6f}")
            diag.selected_key = FirstActionKey.from_decision(best)
            return self._emit(
                observation,
                routes=best.routes,
                newly=sanitize_newly_accepted(observation, [c for c in best.newly_accepted if c in served]),
                rejected=list(best.rejected),
                deferred=list(best.deferred),
                notes=notes,
                status="CERTIFIED_FEASIBLE",
                fallback=False,
                no_cont=False,
                started=started,
                trigger=trigger,
                served=served,
            )

        # Fallback path: persistent certificate, else empty routes.
        self.profile.fallbacks += 1
        if prev_ok and fallback_routes is not None:
            notes.append("fallback_persistent_certificate")
            return self._emit(
                observation,
                routes=fallback_routes,
                newly=[],
                rejected=[],
                deferred=[],
                notes=notes,
                status="CERTIFIED_FEASIBLE",
                fallback=True,
                no_cont=False,
                started=started,
                trigger=trigger,
                served=[],
            )
        notes.append("status=UNKNOWN")
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
            served=[],
        )
