"""Decision-focused baseline-anchored predictive CC-E (Stage 3).

Overrides the matched greedy-nominal incumbent only when paired causal advantage
and a confirmation scenario batch both clear a frozen threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    FiniteDemandModel,
    expected_remaining_given_public,
    sample_finite_demand_scenarios,
)
from safe_time_evrp.mpc3c.forecast import ArrivalForecast
from safe_time_evrp.mpc_central.baseline_anchored_predictive_cce import BaselineAnchoredPredictiveCCE
from safe_time_evrp.mpc_central.counterfactual_actions import (
    FirstActionKey,
    generate_counterfactual_actions,
    sanitize_newly_accepted,
    sanitize_rejects,
    sanitize_routes,
)
from safe_time_evrp.mpc_central.decision_advantage import paired_causal_advantage, screen_by_features
from safe_time_evrp.mpc_central.scenario_rollout import is_quiescent

# Frozen before confirmatory evaluation (train/dev selected).
DEFAULT_TAU = 0.5
DEFAULT_CONFIRM = 1
DEFAULT_SCREEN = 3


@dataclass
class DFBAPProfile:
    decisions: int = 0
    incumbent_kept: int = 0
    overrides: int = 0
    screened: int = 0
    paired_evals: int = 0
    deadline_overruns: int = 0
    decide_seconds: list[float] = field(default_factory=list)


class DecisionFocusedBAP:
    """Matched incumbent + feature screen + paired/confirm advantage override."""

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
        rollout_max_events: int = 100,
        tau: float = DEFAULT_TAU,
        n_confirm: int = DEFAULT_CONFIRM,
        screen_keep: int = DEFAULT_SCREEN,
        use_finite_demand: bool = True,
    ) -> None:
        self._full = instance
        self.horizon = horizon
        self.finite_model = finite_model
        self.n_scenarios = max(1, n_scenarios)
        self.energy = energy or NominalLinearEnergy()
        self.time_limit_seconds = time_limit_seconds
        self.seed = seed
        self.alns_iterations = alns_iterations
        self.max_replan_interval = max_replan_interval
        self.rollout_max_events = rollout_max_events
        self.tau = tau
        self.n_confirm = max(1, n_confirm)
        self.screen_keep = max(1, screen_keep)
        self.use_finite_demand = use_finite_demand
        # Reuse Stage-1 repaired BAP shell for matched incumbent + shared store.
        self._shell = BaselineAnchoredPredictiveCCE(
            instance,
            horizon,
            forecast=forecast,
            finite_model=finite_model,
            n_scenarios=n_scenarios,
            alns_iterations=alns_iterations,
            time_limit_seconds=time_limit_seconds,
            seed=seed,
            energy=self.energy,
            max_replan_interval=max_replan_interval,
            rollout_max_events=rollout_max_events,
            allow_override=False,  # we implement override here
            use_finite_demand=use_finite_demand,
        )
        self.profile = DFBAPProfile()
        self.last_validation_status = "UNKNOWN"
        self.last_audit: dict = {}

    @property
    def store(self):
        return self._shell.store

    def _scenarios(self, observation: Observation, *, n: int, seed_offset: int = 0):
        if self.use_finite_demand and self.finite_model is not None:
            return sample_finite_demand_scenarios(
                self.finite_model,
                observation,
                self._full,
                horizon=self.horizon,
                n_scenarios=n,
                seed=self.seed + seed_offset,
            )
        return [[] for _ in range(n)]

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        notes = [
            "decision_focused_bap",
            f"tau={self.tau}",
            f"n_confirm={self.n_confirm}",
            "quiescent" if is_quiescent(observation) else "busy_epoch",
        ]
        # 1) Matched incumbent via zero-override shell (shared store).
        incumb = self._shell.decide(observation, trigger)
        public = make_public_snapshot(self._full, observation, self.horizon).instance
        rem = 0.0
        if self.finite_model is not None:
            rem = float(
                expected_remaining_given_public(self.finite_model, self._full, observation, horizon=self.horizon).get(
                    "expected_remaining", 0.0
                )
            )
        notes.append(f"expected_remaining={rem:.3f}")

        if perf_counter() - started > self.time_limit_seconds * 0.85:
            self.profile.incumbent_kept += 1
            self.profile.decisions += 1
            self.profile.decide_seconds.append(perf_counter() - started)
            notes.append("anytime_keep_incumbent")
            self.last_validation_status = self._shell.last_validation_status
            return Decision(
                time=incumb.time,
                routes={k: list(v) for k, v in incumb.routes.items()},
                accepted=list(incumb.accepted),
                newly_accepted=list(incumb.newly_accepted),
                rejected=list(incumb.rejected),
                deferred=list(incumb.deferred),
                fallback_used=incumb.fallback_used,
                no_feasible_continuation=incumb.no_feasible_continuation,
                horizon_extended=False,
                planned_service=list(incumb.planned_service),
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=perf_counter() - started,
                trigger=trigger,
                locked_destinations=dict(incumb.locked_destinations),
                notes=list(incumb.notes) + notes,
            )

        # 2) Alternatives + feature screen.
        cands, _ = generate_counterfactual_actions(
            self._full,
            observation,
            horizon=self.horizon,
            energy=self.energy,
            alns_iterations=self.alns_iterations,
            alns_time=max(0.05, self.time_limit_seconds * 0.2),
            seed=self.seed,
            include_solver_baselines=True,
            include_b1=True,
        )
        named = []
        inc_key = FirstActionKey.from_decision(incumb)
        for n, c in cands:
            c2 = Decision(
                time=observation.time,
                routes=sanitize_routes(observation, c.routes),
                accepted=list(observation.accepted),
                newly_accepted=sanitize_newly_accepted(observation, list(c.newly_accepted)),
                rejected=sanitize_rejects(observation, [x for x in c.rejected if x not in c.newly_accepted]),
                deferred=list(c.deferred),
                fallback_used=False,
                no_feasible_continuation=False,
                horizon_extended=False,
                planned_service=list(c.planned_service),
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=0.0,
                trigger=n,
                locked_destinations={},
                notes=list(c.notes),
            )
            if FirstActionKey.from_decision(c2) != inc_key:
                named.append((n, c2))
        screened = screen_by_features(observation, incumb, named, expected_remaining=rem, keep=self.screen_keep)
        self.profile.screened += len(screened)
        notes.append(f"n_screened={len(screened)}")

        scenarios = self._scenarios(observation, n=self.n_scenarios, seed_offset=0)
        confirm = self._scenarios(observation, n=self.n_confirm, seed_offset=101)

        best = None
        best_delta = None
        for n, cand, feat in screened:
            if perf_counter() - started > self.time_limit_seconds:
                notes.append("deadline_during_paired_eval")
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
            est = paired_causal_advantage(
                self._full,
                observation,
                n,
                cand,
                incumb,
                scenarios,
                horizon=self.horizon,
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
            )
            self.profile.paired_evals += 1
            if est.paired_delta is None or est.paired_delta <= self.tau:
                continue
            # Confirmation batch (independent seed offset).
            est2 = paired_causal_advantage(
                self._full,
                observation,
                n,
                cand,
                incumb,
                confirm,
                horizon=self.horizon,
                max_replan_interval=self.max_replan_interval,
                max_events=self.rollout_max_events,
                energy=self.energy,
            )
            if est2.paired_delta is None or est2.paired_delta < self.tau:
                notes.append(f"reject_confirm_{n}")
                continue
            if best_delta is None or est.paired_delta > best_delta:
                best_delta = est.paired_delta
                best = (n, cand, list(rep.served), feat, est.paired_delta, est2.paired_delta)

        elapsed = perf_counter() - started
        if elapsed > self.time_limit_seconds:
            self.profile.deadline_overruns += 1
        self.profile.decide_seconds.append(elapsed)
        self.profile.decisions += 1

        if best is None:
            self.profile.incumbent_kept += 1
            notes.append("keep_incumbent")
            self.last_validation_status = self._shell.last_validation_status
            self.last_audit = {"override": False}
            return Decision(
                time=incumb.time,
                routes={k: list(v) for k, v in incumb.routes.items()},
                accepted=list(incumb.accepted),
                newly_accepted=list(incumb.newly_accepted),
                rejected=list(incumb.rejected),
                deferred=list(incumb.deferred),
                fallback_used=incumb.fallback_used,
                no_feasible_continuation=incumb.no_feasible_continuation,
                horizon_extended=False,
                planned_service=list(incumb.planned_service),
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=elapsed,
                trigger=trigger,
                locked_destinations=dict(incumb.locked_destinations),
                notes=list(incumb.notes) + notes,
            )

        # Override with store sync via shell helper.
        name, cand, served, feat, d1, d2 = best
        self.profile.overrides += 1
        notes.extend([f"override={name}", f"delta={d1:.3f}", f"confirm={d2:.3f}", f"feat={feat:.3f}"])
        self._shell._sync_store_after_choice(
            observation,
            Decision(
                time=observation.time,
                routes=cand.routes,
                accepted=list(observation.accepted) + list(cand.newly_accepted),
                newly_accepted=list(cand.newly_accepted),
                rejected=list(cand.rejected),
                deferred=list(cand.deferred),
                fallback_used=False,
                no_feasible_continuation=False,
                horizon_extended=False,
                planned_service=[],
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=0.0,
                trigger=trigger,
                locked_destinations={},
                notes=["df_bap_override"],
            ),
            served,
        )
        newly = sanitize_newly_accepted(observation, [c for c in cand.newly_accepted if c in served])
        accepted = list(observation.accepted)
        for c in newly:
            if c not in accepted:
                accepted.append(c)
        # Independent verify
        rep = validate_continuation(public, observation, cand.routes, energy=self.energy, require_new=frozenset(newly))
        status = "CERTIFIED_FEASIBLE" if rep.ok else "UNKNOWN"
        if not rep.ok:
            notes.append("override_demoted")
            self.profile.incumbent_kept += 1
            self.profile.overrides -= 1
            self.last_validation_status = self._shell.last_validation_status
            return Decision(
                time=incumb.time,
                routes={k: list(v) for k, v in incumb.routes.items()},
                accepted=list(incumb.accepted),
                newly_accepted=list(incumb.newly_accepted),
                rejected=list(incumb.rejected),
                deferred=list(incumb.deferred),
                fallback_used=True,
                no_feasible_continuation=False,
                horizon_extended=False,
                planned_service=list(incumb.planned_service),
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=elapsed,
                trigger=trigger,
                locked_destinations=dict(incumb.locked_destinations),
                notes=list(incumb.notes) + notes,
            )
        self.last_validation_status = status
        self.last_audit = {"override": True, "delta": d1, "confirm": d2}
        return Decision(
            time=observation.time,
            routes=cand.routes,
            accepted=accepted,
            newly_accepted=newly,
            rejected=sanitize_rejects(observation, [c for c in cand.rejected if c not in newly]),
            deferred=list(cand.deferred),
            fallback_used=False,
            no_feasible_continuation=False,
            horizon_extended=False,
            planned_service=sorted({v.node_id for vs in cand.routes.values() for v in vs if v.purpose == "service"}),
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=elapsed,
            trigger=trigger,
            locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
            notes=notes,
        )
