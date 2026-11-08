"""M1 — Event-aware certificate-carrying ALNS–MPC.

Same plant and ALNS engine as B0/B1. Uses incremental route-resource evaluation
inside ALNS (optional) and cross-event certificate retention with exact-anchor
compatibility. Nominal physics only — not robust recursive feasibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.certificate_store import CertificateStore
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.commitment_safe_mpc.route_resource_profile import EvalMode
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit


@dataclass
class M1Profile:
    decisions: int = 0
    validation_seconds: float = 0.0
    certificate_reuses: int = 0
    certificate_invalidations: int = 0
    routes_revalidated: int = 0
    notes: list[str] = field(default_factory=list)


class CertificateCarryingAlnsMpc:
    """M1 controller."""

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
        eval_mode: EvalMode | str = EvalMode.INCREMENTAL_EVALUATION,
        reuse_certificates: bool = True,
    ) -> None:
        self._full = instance
        self.horizon = horizon
        self.energy = energy or NominalLinearEnergy()
        self.reuse_certificates = reuse_certificates
        self._alns = ReactiveAlnsMpc(
            instance,
            horizon,
            energy=self.energy,
            iterations=iterations,
            time_limit_seconds=time_limit_seconds,
            seed=seed,
            destroy_fraction=destroy_fraction,
            eval_mode=eval_mode,
        )
        self.store = CertificateStore()
        self.profile = M1Profile()
        self.last_validation_status = "UNKNOWN"
        self._verified_routes: dict[str, list[Visit]] | None = None

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full, observation, self.horizon)
        public = snapshot.instance
        this_val = 0.0
        notes = ["certificate_carrying_alns_mpc", f"eval_mode={self._alns.eval_mode.value}"]

        prev_ok = False
        if self.reuse_certificates:
            retained = self.store.advance_or_invalidate(observation)
            if retained is not None:
                rep = validate_continuation(public, observation, retained.routes, energy=self.energy)
                this_val += rep.seconds
                self.profile.validation_seconds += rep.seconds
                self.profile.routes_revalidated += rep.routes_checked
                if rep.ok:
                    prev_ok = True
                    self._verified_routes = {vid: list(vs) for vid, vs in retained.routes.items()}
                    self.profile.certificate_reuses += 1
                    notes.append("certificate_revalidated_ok")
                else:
                    self.store.invalidate_count += 1
                    self.store.current = None
                    self._verified_routes = None
                    self.profile.certificate_invalidations += 1
                    notes.append("certificate_invalidated_on_recheck")
            elif self.store.invalidate_count:
                self.profile.certificate_invalidations = self.store.invalidate_count

        raw = self._alns.decide(observation, trigger)
        candidate_routes = raw.routes
        proposed_new = list(raw.newly_accepted)

        report = validate_continuation(
            public,
            observation,
            candidate_routes,
            energy=self.energy,
            require_new=frozenset(proposed_new),
        )
        this_val += report.seconds
        self.profile.validation_seconds += report.seconds
        self.profile.routes_revalidated += report.routes_checked
        self.profile.decisions += 1

        newly: list[str] = []
        status = report.status
        routes = candidate_routes

        if report.ok:
            newly = [c for c in proposed_new if c in report.served]
            self._verified_routes = {vid: list(vs) for vid, vs in routes.items()}
            self.store.publish(routes, observation, report.served)
            status = "CERTIFIED_FEASIBLE"
            notes.append("validated_with_new_accepts" if newly else "validated_commitments_only")
        else:
            report2 = validate_continuation(
                public, observation, candidate_routes, energy=self.energy, require_new=frozenset()
            )
            this_val += report2.seconds
            self.profile.validation_seconds += report2.seconds
            if report2.ok and self._alns._covers_commitments(observation, report2.served):
                newly = []
                routes = candidate_routes
                status = "CERTIFIED_FEASIBLE"
                self._verified_routes = {vid: list(vs) for vid, vs in routes.items()}
                self.store.publish(routes, observation, report2.served)
                notes.append("rejected_unvalidated_new_accepts")
            elif prev_ok and self._verified_routes is not None:
                routes = self._verified_routes
                newly = []
                status = "CERTIFIED_FEASIBLE"
                notes.append("reused_revalidated_previous_certificate")
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
        planned = [v.node_id for vs in routes.values() for v in vs if v.purpose == "service"]
        elapsed = perf_counter() - started
        overrun = elapsed > self._alns.time_limit_seconds
        audit = dict(raw.audit or {})
        audit["validation_status"] = status
        audit["validation_seconds_this_decision"] = this_val
        audit["validation_seconds_cumulative"] = self.profile.validation_seconds
        audit["validation_seconds"] = this_val
        audit["m1"] = {
            "certificate_reuses": self.profile.certificate_reuses,
            "certificate_invalidations": self.profile.certificate_invalidations,
            "reuse_certificates": self.reuse_certificates,
            "eval_mode": self._alns.eval_mode.value,
            "eval_stats": (raw.audit or {}).get("alns", {}).get("eval_stats"),
            "deadline_overrun": overrun,
        }
        if overrun:
            notes.append("cooperative_deadline_overrun_observed")

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
