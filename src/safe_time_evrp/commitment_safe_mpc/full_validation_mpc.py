"""B1 — Full-Validation Commitment-Safe ALNS–MPC.

Reuses ``ReactiveAlnsMpc`` as the search engine. Every acceptance and dispatch
requires an independently validated nominal continuation witness.

Not a robust recursive-feasibility guarantee against unknown disturbances.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit


@dataclass
class RevalidationProfile:
    decisions: int = 0
    routes_revalidated: int = 0
    charge_checks: int = 0
    obligations_rechecked: int = 0
    validation_seconds: float = 0.0
    previous_witness_still_feasible: int = 0
    previous_witness_invalidated: int = 0
    notes: list[str] = field(default_factory=list)


class FullValidationAlnsMpc:
    """B1 controller: same ALNS engine + independent full validation gate."""

    def __init__(
        self,
        instance: Instance,
        horizon: float,
        *,
        energy: NominalLinearEnergy | None = None,
        iterations: int = 40,
        time_limit_seconds: float = 0.25,
        seed: int = 0,
        destroy_fraction: float = 0.35,
    ) -> None:
        self._full = instance
        self.horizon = horizon
        self.energy = energy or NominalLinearEnergy()
        self._alns = ReactiveAlnsMpc(
            instance,
            horizon,
            energy=self.energy,
            iterations=iterations,
            time_limit_seconds=time_limit_seconds,
            seed=seed,
            destroy_fraction=destroy_fraction,
        )
        self._verified_routes: dict[str, list[Visit]] | None = None
        self.profile = RevalidationProfile()
        self.last_validation_status = "UNKNOWN"

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        public = snapshot.instance

        this_decision_validation = 0.0
        # Revalidate previous witness against current anchors
        prev_ok = False
        if self._verified_routes is not None:
            prev = validate_continuation(public, observation, self._verified_routes, energy=self.energy)
            this_decision_validation += prev.seconds
            self.profile.validation_seconds += prev.seconds
            self.profile.routes_revalidated += prev.routes_checked
            self.profile.charge_checks += prev.charge_visits_checked
            self.profile.obligations_rechecked += prev.obligations_rechecked
            if prev.ok:
                prev_ok = True
                self.profile.previous_witness_still_feasible += 1
            else:
                self.profile.previous_witness_invalidated += 1
                self._verified_routes = None

        raw = self._alns.decide(observation, trigger)
        # Strip unvalidated new accepts until we certify
        candidate_routes = raw.routes
        proposed_new = list(raw.newly_accepted)

        # Try to certify with proposed accepts; if fail, drop new accepts and re-check commitments only
        report = validate_continuation(
            public,
            observation,
            candidate_routes,
            energy=self.energy,
            require_new=frozenset(proposed_new),
        )
        this_decision_validation += report.seconds
        self.profile.validation_seconds += report.seconds
        self.profile.routes_revalidated += report.routes_checked
        self.profile.charge_checks += report.charge_visits_checked
        self.profile.obligations_rechecked += report.obligations_rechecked
        self.profile.decisions += 1

        newly: list[str] = []
        status = report.status
        routes = candidate_routes
        notes = list(raw.notes) + ["full_validation_mpc"]

        if report.ok:
            newly = [c for c in proposed_new if c in report.served]
            self._verified_routes = {vid: list(vs) for vid, vs in routes.items()}
            status = "CERTIFIED_FEASIBLE"
            notes.append("validated_with_new_accepts" if newly else "validated_commitments_only")
        else:
            # Fallback: validate without new accepts
            report2 = validate_continuation(
                public, observation, candidate_routes, energy=self.energy, require_new=frozenset()
            )
            this_decision_validation += report2.seconds
            self.profile.validation_seconds += report2.seconds
            self.profile.routes_revalidated += report2.routes_checked
            if report2.ok and self._alns._covers_commitments(observation, report2.served):
                newly = []
                routes = candidate_routes
                status = "CERTIFIED_FEASIBLE"
                self._verified_routes = {vid: list(vs) for vid, vs in routes.items()}
                notes.append("rejected_unvalidated_new_accepts")
                notes.extend(report.reasons[:3])
            elif prev_ok and self._verified_routes is not None:
                routes = self._verified_routes
                newly = []
                status = "CERTIFIED_FEASIBLE"
                notes.append("reused_revalidated_previous_witness")
            else:
                newly = []
                routes = {v.id: [] for v in observation.vehicles}
                status = "UNKNOWN"
                notes.append("status=UNKNOWN")
                notes.extend(report.reasons[:4])

        self.last_validation_status = status
        accepted = list(observation.accepted)
        for c in newly:
            if c not in accepted:
                accepted.append(c)

        planned = []
        for visits in routes.values():
            planned.extend(v.node_id for v in visits if v.purpose == "service")

        elapsed = perf_counter() - started
        audit = dict(raw.audit or {})
        audit["validation_status"] = status
        audit["validation_seconds_this_decision"] = this_decision_validation
        audit["validation_seconds_cumulative"] = self.profile.validation_seconds
        # Backward-compatible alias = per-decision increment (not cumulative).
        audit["validation_seconds"] = this_decision_validation
        audit["validation_reasons"] = report.reasons[:6]
        audit["revalidation"] = {
            "routes_revalidated": self.profile.routes_revalidated,
            "charge_checks": self.profile.charge_checks,
            "obligations_rechecked": self.profile.obligations_rechecked,
            "previous_still_feasible": self.profile.previous_witness_still_feasible,
            "previous_invalidated": self.profile.previous_witness_invalidated,
        }

        return Decision(
            time=observation.time,
            routes=routes,
            accepted=accepted,
            newly_accepted=newly,
            rejected=[c for c in raw.rejected if c not in newly],
            deferred=list(raw.deferred),
            fallback_used=status != "CERTIFIED_FEASIBLE" and prev_ok,
            no_feasible_continuation=status != "CERTIFIED_FEASIBLE",
            horizon_extended=raw.horizon_extended,
            planned_service=sorted(set(planned)),
            total_distance=raw.total_distance if status == "CERTIFIED_FEASIBLE" else 0.0,
            total_charge_time=raw.total_charge_time if status == "CERTIFIED_FEASIBLE" else 0.0,
            optimize_seconds=elapsed,
            trigger=trigger,
            locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
            notes=notes,
            audit=audit,
        )
