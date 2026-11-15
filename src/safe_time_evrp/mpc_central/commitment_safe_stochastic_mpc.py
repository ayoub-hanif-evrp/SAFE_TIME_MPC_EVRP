"""Commitment-Safe Stochastic Model Predictive Control (proposed method).

Approximation class (honest)
----------------------------
This controller implements a **restricted candidate-set stochastic MPC** with
scenario-dependent B1-validated recourse (a rollout / policy-search approximation
of the extensive-form problem in
``docs/methodology/COMMITMENT_SAFE_STOCHASTIC_MPC.md``).

It does **not** claim to solve the full multi-stage stochastic MIP.

First-stage (shared / nonanticipative) variables optimized over a discrete set:
  newly_accepted, rejected, route certificate, first executable legs.

Scenario recourse: ``B1ValidatedRecourse`` inside horizon projection / scoring.

Hard constraints: stage-0 commitment coverage; horizon-end terminal commitment;
locks; public-information only.

Soft objective: fixed economic weights (service − AU − distance).

Transactional emission: certificates and new accepts commit only after
independent validation; failed candidates never leave speculative accepts in
the Decision returned to the plant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.certificate_store import CertificateStore
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import assert_no_future_leak, make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, ForecastCustomer
from safe_time_evrp.mpc_central.causal_plant import DISTANCE_PENALTY, SERVICE_REWARD, UNFULFILLED_PENALTY
from safe_time_evrp.mpc_central.counterfactual_actions import (
    CounterfactualDiagnostics,
    FirstActionKey,
    generate_counterfactual_actions,
    sanitize_newly_accepted,
    sanitize_rejects,
    sanitize_routes,
)
from safe_time_evrp.mpc_central.scenario_rollout import expected_rollout_value, is_quiescent
from safe_time_evrp.mpc_central.terminal_commitment import (
    TerminalRejectReason,
    project_to_horizon,
)

# Fixed economic weights for controlled comparisons (do not retune on test instances).
OBJECTIVE_WEIGHTS = {
    "service_reward": SERVICE_REWARD,
    "unfulfilled_penalty": UNFULFILLED_PENALTY,
    "distance_penalty": DISTANCE_PENALTY,
}

STATUS_CERTIFIED = "CERTIFIED_FEASIBLE"
STATUS_LOST = "CERTIFIED_FEASIBILITY_LOST"
STATUS_UNKNOWN = "UNKNOWN"  # only when no existing obligations need coverage


@dataclass
class CssMpcProfile:
    decisions: int = 0
    scenarios_evaluated: int = 0
    causal_rollouts: int = 0
    validation_seconds: float = 0.0
    candidate_gen_seconds: float = 0.0
    scoring_seconds: float = 0.0
    terminal_seconds: float = 0.0
    fallbacks: int = 0
    certificate_reuses: int = 0
    certificate_invalidations: int = 0
    certificate_publishes: int = 0
    deadline_overruns: int = 0
    terminal_rejects: int = 0
    rollout_rejects: int = 0
    stage0_rejects: int = 0
    transactional_demotions: int = 0
    decide_seconds: list[float] = field(default_factory=list)
    last_diagnostics: CounterfactualDiagnostics | None = None
    notes: list[str] = field(default_factory=list)


class CommitmentSafeStochasticMpc:
    """Proposed Commitment-Safe Stochastic MPC (receding-horizon, first-action)."""

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
        finite_demand_model=None,
        use_finite_demand: bool = False,
        require_terminal_commitment: bool = True,
        adaptive_scenarios: bool = True,
        scenario_override: list[list[ForecastCustomer]] | None = None,
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
        self.finite_demand_model = finite_demand_model
        self.use_finite_demand = use_finite_demand
        self.require_terminal_commitment = require_terminal_commitment
        self.adaptive_scenarios = adaptive_scenarios
        self.scenario_override = scenario_override
        self.store = CertificateStore()
        self._last_certified_routes: dict[str, list[Visit]] | None = None
        self._last_solution_routes: dict[str, list[Visit]] | None = None
        self.profile = CssMpcProfile()
        self.last_validation_status = STATUS_UNKNOWN
        self.last_audit: dict = {}
        self.last_obligation_gap: list[str] = []
        self.objective_weights = dict(OBJECTIVE_WEIGHTS)
        self.approximation_class = (
            "restricted_candidate_set_stochastic_mpc_with_scenario_b1_recourse"
        )

    def _scenario_forecasts(self, observation: Observation, *, n: int | None = None) -> list[list[ForecastCustomer]]:
        """Nonanticipative scenarios: measurable w.r.t. current public information only."""
        n_sc = n if n is not None else self.n_scenarios
        if self.scenario_override is not None:
            return list(self.scenario_override)[:n_sc]
        if not self.use_forecast:
            return [[]]
        if self.use_finite_demand and self.finite_demand_model is not None:
            from safe_time_evrp.mpc3c.finite_demand_forecast import sample_finite_demand_scenarios

            return sample_finite_demand_scenarios(
                self.finite_demand_model,
                observation,
                self._full,
                horizon=self.horizon,
                n_scenarios=n_sc,
                seed=self.seed,
            )
        if self.forecast is None:
            return [[]]
        from safe_time_evrp.mpc3c.forecast import visible_forecast

        return [
            visible_forecast(observation, self.forecast, self.horizon, scenario_index=s_idx)
            for s_idx in range(n_sc)
        ]

    def _pending_existing(self, observation: Observation) -> set[str]:
        return set(observation.accepted) - set(observation.completed) - set(observation.in_service)

    def _finalize_decision(
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
        publish: bool,
        served: list[str] | None = None,
    ) -> Decision:
        """Build the Decision after commit decisions are already resolved transactionally."""
        routes = sanitize_routes(observation, routes)
        newly = sanitize_newly_accepted(observation, newly)
        rejected = sanitize_rejects(observation, [c for c in rejected if c not in newly])
        # accepted list mirrors plant post-decision obligations we are willing to claim.
        accepted = list(observation.accepted)
        for c in newly:
            if c not in accepted:
                accepted.append(c)

        pending = set(accepted) - set(observation.completed) - set(observation.in_service)
        if status == STATUS_CERTIFIED and pending:
            self.last_obligation_gap = []
        elif pending:
            notes.append(f"uncovered_accepted_obligations:{sorted(self._pending_existing(observation))}")
            self.last_obligation_gap = sorted(self._pending_existing(observation))
            no_cont = True
        else:
            self.last_obligation_gap = []

        planned = [v.node_id for vs in routes.values() for v in vs if v.purpose == "service"]
        elapsed = perf_counter() - started
        self.profile.decide_seconds.append(elapsed)
        if elapsed > self.time_limit_seconds:
            self.profile.deadline_overruns += 1
            notes.append("deadline_overrun")

        self.last_validation_status = status
        self.last_audit = {
            "controller": "commitment_safe_stochastic_mpc",
            "validation_status": status,
            "fallback": fallback,
            "published": publish,
            "objective_weights": dict(self.objective_weights),
            "require_terminal_commitment": self.require_terminal_commitment,
            "n_scenarios": self.n_scenarios,
            "first_action_only": True,
            "receding_horizon": True,
            "approximation_class": self.approximation_class,
            "transactional_emit": True,
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
            audit={"css_mpc": self.last_audit},
        )

    def _try_commit(
        self,
        observation: Observation,
        public: Instance,
        *,
        routes: dict[str, list[Visit]],
        newly: list[str],
        rejected: list[str],
        deferred: list[str],
        notes: list[str],
        started: float,
        trigger: str,
        fallback_flag: bool,
    ) -> Decision | None:
        """Validate candidate without mutating store; publish only on success.

        Returns a Decision if commit succeeds, else None (caller must fallback).
        """
        routes = sanitize_routes(observation, routes)
        newly = sanitize_newly_accepted(observation, newly)
        rejected = sanitize_rejects(observation, [c for c in rejected if c not in newly])
        rep = validate_continuation(
            public,
            observation,
            routes,
            energy=self.energy,
            require_new=frozenset(newly),
        )
        self.profile.validation_seconds += rep.seconds
        if not rep.ok:
            notes.append("commit_validation_failed")
            notes.extend(rep.reasons[:3])
            self.profile.transactional_demotions += 1
            return None

        accepted_set = frozenset(list(observation.accepted) + list(newly))
        self.store.publish(routes, observation, list(rep.served), accepted=accepted_set)
        self.profile.certificate_publishes += 1
        self._last_certified_routes = {vid: list(vs) for vid, vs in routes.items()}
        self._last_solution_routes = {vid: list(vs) for vid, vs in routes.items()}
        notes.append("transactional_commit_ok")
        return self._finalize_decision(
            observation,
            routes=routes,
            newly=newly,
            rejected=rejected,
            deferred=deferred,
            notes=notes,
            status=STATUS_CERTIFIED,
            fallback=fallback_flag,
            no_cont=False,
            started=started,
            trigger=trigger,
            publish=True,
            served=list(rep.served),
        )

    def _emit_fallback(
        self,
        observation: Observation,
        public: Instance,
        *,
        fallback_routes: dict[str, list[Visit]] | None,
        notes: list[str],
        started: float,
        trigger: str,
        rejected: list[str] | None = None,
        deferred: list[str] | None = None,
    ) -> Decision:
        """Emit verified backup with **zero** speculative new accepts, or report loss."""
        self.profile.fallbacks += 1
        notes = list(notes)
        notes.append("fallback_path_no_new_accepts")

        if fallback_routes is not None:
            committed = self._try_commit(
                observation,
                public,
                routes=fallback_routes,
                newly=[],
                rejected=list(rejected or []),
                deferred=list(deferred or []),
                notes=notes + ["fallback_verified_incumbent"],
                started=started,
                trigger=trigger,
                fallback_flag=True,
            )
            if committed is not None:
                return committed

        # No valid backup for existing obligations.
        existing = self._pending_existing(observation)
        if existing:
            notes.append("status=CERTIFIED_FEASIBILITY_LOST")
            notes.append("existing_obligations_uncovered_by_fallback")
            return self._finalize_decision(
                observation,
                routes={v.id: [] for v in observation.vehicles},
                newly=[],  # never introduce accepts
                rejected=list(rejected or []),
                deferred=list(deferred or []),
                notes=notes,
                status=STATUS_LOST,
                fallback=True,
                no_cont=True,
                started=started,
                trigger=trigger,
                publish=False,
            )

        notes.append("status=UNKNOWN")
        return self._finalize_decision(
            observation,
            routes={v.id: [] for v in observation.vehicles},
            newly=[],
            rejected=list(rejected or []),
            deferred=list(deferred or []),
            notes=notes,
            status=STATUS_UNKNOWN,
            fallback=True,
            no_cont=True,
            started=started,
            trigger=trigger,
            publish=False,
        )

    def _terminal_filter(
        self,
        observation: Observation,
        cand: Decision,
        scenario_fcs: list[list[ForecastCustomer]],
        *,
        deadline: float,
    ) -> tuple[bool, str]:
        """Require terminal commitment OK on every scored scenario (or empty-future)."""
        if not self.require_terminal_commitment:
            return True, "terminal_disabled"
        scenarios = scenario_fcs if scenario_fcs else [[]]
        for s_idx, fcs in enumerate(scenarios):
            if perf_counter() > deadline:
                self.profile.terminal_rejects += 1
                return False, "budget"
            report, _ = project_to_horizon(
                self._full,
                observation,
                cand,
                fcs,
                horizon=self.horizon,
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
                deadline=deadline,
            )
            self.profile.terminal_seconds += report.seconds
            if report.reason == TerminalRejectReason.BUDGET:
                self.profile.terminal_rejects += 1
                return False, "budget"
            if report.reason in {
                TerminalRejectReason.ROLLOUT_FAILED,
                TerminalRejectReason.REPLAY_FAILED,
            }:
                self.profile.rollout_rejects += 1
                return False, f"rollout:{report.reason.value}:{report.detail}"
            if not report.ok:
                self.profile.terminal_rejects += 1
                return False, f"terminal_infeasible:sc{s_idx}:{report.detail}"
        return True, "terminal_ok"

    def solve_mpc(self, observation: Observation, trigger: str) -> Decision:
        return self.decide(observation, trigger)

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        deadline = started + self.time_limit_seconds
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        assert_no_future_leak(snapshot, self._full)
        public = snapshot.instance
        notes = [
            "commitment_safe_stochastic_mpc",
            "receding_horizon=1",
            "first_action_execution=1",
            "scoring_mode=causal_economic",
            "transactional_emit=1",
            f"use_forecast={int(self.use_forecast)}",
            f"terminal_commitment={int(self.require_terminal_commitment)}",
            "quiescent" if is_quiescent(observation) else "busy_epoch",
            f"approximation={self.approximation_class}",
            f"service_reward={SERVICE_REWARD}",
            f"au_penalty={UNFULFILLED_PENALTY}",
            f"distance_penalty={DISTANCE_PENALTY}",
        ]

        # --- Warm-start incumbent ---
        prev_ok = False
        fallback_routes: dict[str, list[Visit]] | None = None
        retained = self.store.advance_or_invalidate(observation)
        if retained is not None:
            rep = validate_continuation(public, observation, retained.routes, energy=self.energy)
            self.profile.validation_seconds += rep.seconds
            if rep.ok:
                prev_ok = True
                fallback_routes = {vid: list(vs) for vid, vs in retained.routes.items()}
                self._last_certified_routes = {vid: list(vs) for vid, vs in retained.routes.items()}
                self.profile.certificate_reuses += 1
                notes.append("warm_start_certificate_ok")
            else:
                self.store.invalidate_count += 1
                self.store.current = None
                self.profile.certificate_invalidations += 1
                notes.append("certificate_invalidated_on_recheck")
        if not prev_ok and self._last_certified_routes is not None:
            rep2 = validate_continuation(public, observation, self._last_certified_routes, energy=self.energy)
            self.profile.validation_seconds += rep2.seconds
            if rep2.ok:
                prev_ok = True
                fallback_routes = {vid: list(vs) for vid, vs in self._last_certified_routes.items()}
                notes.append("warm_start_last_certified_ok")
                self.profile.certificate_reuses += 1

        # --- Candidate generation (ALNS as internal subroutine) ---
        t_gen = perf_counter()
        remaining = max(0.05, deadline - perf_counter())
        alns_time = max(0.05, min(remaining * 0.35, self.time_limit_seconds * 0.3))
        candidates, diag = generate_counterfactual_actions(
            self._full,
            observation,
            horizon=self.horizon,
            energy=self.energy,
            alns_iterations=self.alns_iterations,
            alns_time=alns_time,
            seed=self.seed,
            include_solver_baselines=True,
            include_b1=True,
        )
        self.profile.candidate_gen_seconds += perf_counter() - t_gen
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

        # Adaptive scenario count under remaining budget.
        n_sc = self.n_scenarios
        if self.adaptive_scenarios and self.use_forecast:
            rem = deadline - perf_counter()
            if rem < 0.15 * self.time_limit_seconds:
                n_sc = 1
            notes.append(f"adaptive_n_scenarios={n_sc}")
        scenario_fcs = self._scenario_forecasts(observation, n=n_sc)
        notes.append(f"n_scenarios_scored={len(scenario_fcs)}")

        scored: list[tuple[float, str, Decision, list[str]]] = []
        t_score = perf_counter()
        for name, cand in candidates:
            if perf_counter() >= deadline:
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
            # Hard stage-0 commitment.
            report = validate_continuation(
                public,
                observation,
                cand.routes,
                energy=self.energy,
                require_new=frozenset(cand.newly_accepted),
            )
            self.profile.validation_seconds += report.seconds
            if not report.ok:
                self.profile.stage0_rejects += 1
                continue

            # Distinct horizon-end terminal commitment (Gate 2).
            term_ok, term_detail = self._terminal_filter(
                observation, cand, scenario_fcs, deadline=deadline
            )
            if not term_ok:
                notes.append(f"reject:{name}:{term_detail}")
                continue

            mean_v, scores = expected_rollout_value(
                self._full,
                observation,
                cand,
                scenario_fcs,
                horizon=self.horizon,
                max_scenarios=len(scenario_fcs),
                scoring_mode="causal",
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
            )
            self.profile.scenarios_evaluated += len(scores)
            self.profile.causal_rollouts += len(scores)
            if mean_v <= -1e8:
                self.profile.rollout_rejects += 1
                continue
            scored.append((mean_v, name, cand, list(report.served)))
        self.profile.scoring_seconds += perf_counter() - t_score
        self.profile.decisions += 1

        if scored:

            def _rank(item: tuple[float, str, Decision, list[str]]):
                value, name, cand, _served = item
                key = FirstActionKey.from_decision(cand)
                n_service = sum(1 for leg in key.first_legs if leg[2] == "service")
                n_charge = sum(1 for leg in key.first_legs if leg[2] == "charge")
                not_wait = 0 if name.startswith("wait") or name == "wait_idle" else 1
                return (value, n_charge, n_service, len(key.newly_accepted), not_wait, name)

            scored.sort(key=_rank, reverse=True)
            best_v, best_name, best, served = scored[0]
            notes.append(f"selected={best_name}")
            notes.append(f"expected_value={best_v:.6f}")
            diag.selected_key = FirstActionKey.from_decision(best)
            # Transactional commit: only keep new accepts that appear in validated served set
            # AND pass independent re-validation inside _try_commit.
            newly = sanitize_newly_accepted(
                observation, [c for c in best.newly_accepted if c in served]
            )
            committed = self._try_commit(
                observation,
                public,
                routes=best.routes,
                newly=newly,
                rejected=list(best.rejected),
                deferred=list(best.deferred),
                notes=notes,
                started=started,
                trigger=trigger,
                fallback_flag=False,
            )
            if committed is not None:
                return committed
            # Speculative winner failed final commit — discard new accepts, use backup.
            notes.append("winner_commit_failed_discard_new_accepts")

        return self._emit_fallback(
            observation,
            public,
            fallback_routes=fallback_routes if prev_ok else None,
            notes=notes,
            started=started,
            trigger=trigger,
        )
