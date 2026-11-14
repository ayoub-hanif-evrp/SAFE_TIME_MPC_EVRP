"""Commitment-viability-aware, baseline-anchored switching MPC.

Default executable action is B1. A counterfactual candidate may replace B1 only if:

1. It passes the full nominal commitment-safety gate.
2. Paired expected improvement over B1 exceeds a *prespecified* threshold.
3. A *prespecified* risk test on paired scenario deltas supports the switch.

Thresholds are fixed a priori and are not tuned on Phase 3E development seeds.
Forecast-model bounds are never claimed as misspecification guarantees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.full_validation_mpc import FullValidationAlnsMpc
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, visible_forecast
from safe_time_evrp.mpc_central.counterfactual_actions import (
    FirstActionKey,
    generate_counterfactual_actions,
    sanitize_newly_accepted,
    sanitize_rejects,
    sanitize_routes,
)
from safe_time_evrp.mpc_central.paired_b1_eval import PairedCandidateReport, evaluate_paired_candidate
from safe_time_evrp.mpc_central.scenario_rollout import is_quiescent

# --- A priori switching hyperparameters (NOT fitted on Phase 3E seeds) ---
IMPROVEMENT_THRESHOLD = 0.0
# Require every valid paired scenario to be no worse than this floor.
RISK_FLOOR = 0.0
HOEFFDING_ALPHA = 0.1
# Prefer the unanimous non-negative paired-improvement risk rule for small n;
# Hoeffding LCB is recorded for honesty but is typically non-decisive at n=2.
REQUIRE_HOEFFDING_LCB = False


@dataclass
class SwitchingProfile:
    decisions: int = 0
    switches: int = 0
    b1_defaults: int = 0
    candidates_considered: int = 0
    scoring_seconds: float = 0.0
    last_switch_name: str | None = None
    last_mean_delta: float | None = None
    notes: list[str] = field(default_factory=list)


class CommitmentViabilitySwitchingMpc:
    """Baseline-anchored switching controller (algorithmically ≠ unguarded rollout)."""

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
        rollout_max_events: int = 200,
        use_forecast: bool = True,
        allow_switching: bool = True,
        improvement_threshold: float = IMPROVEMENT_THRESHOLD,
        risk_floor: float = RISK_FLOOR,
        hoeffding_alpha: float = HOEFFDING_ALPHA,
        require_hoeffding_lcb: bool = REQUIRE_HOEFFDING_LCB,
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
        self.allow_switching = allow_switching
        self.improvement_threshold = improvement_threshold
        self.risk_floor = risk_floor
        self.hoeffding_alpha = hoeffding_alpha
        self.require_hoeffding_lcb = require_hoeffding_lcb
        self._verified: dict | None = None
        # Persistent B1 reference so certificates / verified routes match standalone B1 episodes.
        self._b1 = FullValidationAlnsMpc(
            instance,
            horizon,
            energy=self.energy,
            iterations=alns_iterations,
            time_limit_seconds=time_limit_seconds,
            seed=seed,
        )
        self.profile = SwitchingProfile()
        self.last_validation_status = "UNKNOWN"
        self.last_audit: dict = {}

    def _scenario_forecasts(self, observation: Observation) -> list[list]:
        if not self.use_forecast or self.forecast is None:
            return []
        return [
            visible_forecast(observation, self.forecast, self.horizon, scenario_index=s_idx)
            for s_idx in range(self.n_scenarios)
        ]

    def _sanitize_decision(self, observation: Observation, decision: Decision, *, trigger: str) -> Decision:
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

    @staticmethod
    def _eligible_switch(
        report: PairedCandidateReport, *, threshold: float, risk_floor: float, require_lcb: bool
    ) -> bool:
        if report.name == "b1":
            return False
        if not report.commitment_ok:
            return False
        if report.mean_delta is None or report.min_delta is None:
            return False
        if report.mean_delta <= threshold:
            return False
        if report.min_delta < risk_floor:
            return False
        if require_lcb:
            if report.hoeffding_lcb is None or report.hoeffding_lcb <= threshold:
                return False
        return True

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        notes = [
            "commitment_viability_switching_mpc",
            f"allow_switching={int(self.allow_switching)}",
            f"use_forecast={int(self.use_forecast)}",
            "quiescent" if is_quiescent(observation) else "busy_epoch",
            f"improvement_threshold={self.improvement_threshold}",
            f"risk_floor={self.risk_floor}",
        ]
        # Executable B1 reference from the persistent controller (matched seed/budget/state).
        b1_raw = self._b1.decide(observation, trigger)
        b1 = self._sanitize_decision(observation, b1_raw, trigger="b1_reference")

        scenarios = self._scenario_forecasts(observation)
        reports: list[PairedCandidateReport] = []
        t_score = perf_counter()
        if self.allow_switching and scenarios:
            candidates, _diag = generate_counterfactual_actions(
                self._full,
                observation,
                horizon=self.horizon,
                energy=self.energy,
                alns_iterations=self.alns_iterations,
                alns_time=max(0.05, self.time_limit_seconds * 0.35),
                seed=self.seed,
                include_solver_baselines=True,
                include_b1=False,
            )
            b1_key = FirstActionKey.from_decision(b1)
            seen = {b1_key}
            reports.append(
                evaluate_paired_candidate(
                    self._full,
                    observation,
                    "b1",
                    b1,
                    b1,
                    scenarios,
                    horizon=self.horizon,
                    max_replan_interval=self.max_replan_interval,
                    max_events=self.rollout_max_events,
                    energy=self.energy,
                    alpha=self.hoeffding_alpha,
                )
            )
            for name, cand in candidates:
                cand = self._sanitize_decision(observation, cand, trigger=cand.trigger)
                key = FirstActionKey.from_decision(cand)
                if key in seen:
                    continue
                seen.add(key)
                if perf_counter() - started > self.time_limit_seconds:
                    notes.append("cooperative_deadline_hit")
                    break
                reports.append(
                    evaluate_paired_candidate(
                        self._full,
                        observation,
                        name,
                        cand,
                        b1,
                        scenarios,
                        horizon=self.horizon,
                        max_replan_interval=self.max_replan_interval,
                        max_events=self.rollout_max_events,
                        energy=self.energy,
                        alpha=self.hoeffding_alpha,
                    )
                )
        self.profile.scoring_seconds += perf_counter() - t_score
        self.profile.decisions += 1
        self.profile.candidates_considered += max(0, len(reports) - 1)

        selected_name = "b1"
        switch_meta: dict | None = None
        switched = False
        selected = b1_raw
        if self.allow_switching and scenarios:
            eligible = [
                r
                for r in reports
                if self._eligible_switch(
                    r,
                    threshold=self.improvement_threshold,
                    risk_floor=self.risk_floor,
                    require_lcb=self.require_hoeffding_lcb,
                )
            ]
            if eligible:
                eligible.sort(key=lambda r: (r.mean_delta or -1e18, r.min_delta or -1e18), reverse=True)
                best = eligible[0]
                public = make_public_snapshot(self._full, observation, self.horizon).instance
                cand = self._sanitize_decision(observation, best.candidate, trigger=trigger)
                report = validate_continuation(
                    public,
                    observation,
                    cand.routes,
                    energy=self.energy,
                    require_new=frozenset(cand.newly_accepted),
                )
                if report.ok:
                    selected = cand
                    selected_name = best.name
                    switched = True
                    switch_meta = {
                        "mean_delta": best.mean_delta,
                        "min_delta": best.min_delta,
                        "hoeffding_lcb": best.hoeffding_lcb,
                    }
                    self.profile.switches += 1
                    self.profile.last_switch_name = selected_name
                    self.profile.last_mean_delta = best.mean_delta
                    notes.append(f"switch_to={selected_name}")
                    notes.append(f"mean_delta={best.mean_delta:.4f}")
                else:
                    notes.append("switch_candidate_failed_late_gate")
                    self.profile.b1_defaults += 1
                    notes.append("default_b1")
            else:
                self.profile.b1_defaults += 1
                notes.append("default_b1")
        else:
            self.profile.b1_defaults += 1
            notes.append("default_b1_no_switch_path")

        # When not switching, emit the exact persistent-B1 decision so matched episodes
        # coincide with the standalone B1 baseline (same seed, budget, certificate state).
        if not switched:
            selected = b1_raw
            selected.notes = list(selected.notes) + notes
            selected.optimize_seconds = perf_counter() - started
            selected.audit = {
                "switching_mpc": {
                    "selected": "b1",
                    "switch": None,
                    "n_reports": len(reports),
                    "eligible_switches": 0,
                }
            }
            self.last_audit = selected.audit["switching_mpc"]
            self.last_validation_status = "CERTIFIED_FEASIBLE"
            return selected

        self._verified = {vid: list(vs) for vid, vs in selected.routes.items()}
        self.last_validation_status = "CERTIFIED_FEASIBLE"
        self.last_audit = {
            "selected": selected_name,
            "b1_key": [list(x) for x in FirstActionKey.from_decision(b1).first_legs],
            "switch": switch_meta,
            "n_reports": len(reports),
            "eligible_switches": sum(
                1
                for r in reports
                if self._eligible_switch(
                    r,
                    threshold=self.improvement_threshold,
                    risk_floor=self.risk_floor,
                    require_lcb=self.require_hoeffding_lcb,
                )
            ),
        }
        selected.notes = list(selected.notes) + notes
        selected.optimize_seconds = perf_counter() - started
        selected.trigger = trigger
        selected.audit = {"switching_mpc": self.last_audit}
        return selected
