"""Feasibility-preserving receding-horizon controller.

The backup is replaced only by ``BackupStore.commit`` after a certificate and a
matching action id. A timeout, a crash, or a stale id leaves the backup in place.
"""

from __future__ import annotations

from time import perf_counter

from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.robust.backup import BackupStore, dispatch_suffix, observation_version
from safe_time_evrp.robust.certificate import Certificate, Verdict, certify_routes
from safe_time_evrp.robust.supervisor import SolverSupervisor
from safe_time_evrp.robust.triggers import TriggerDecision, TriggerPolicy, classify
from safe_time_evrp.robust.uncertainty import RectangularUncertainty


def _pending(observation: Observation) -> bool:
    held = set(observation.accepted) | set(observation.in_service) | set(observation.deferred)
    return any(customer_id not in held for customer_id in observation.released_open)


class SafeTimeController:
    def __init__(
        self,
        instance: Instance,
        horizon: float,
        uncertainty: RectangularUncertainty,
        policy: TriggerPolicy,
        deadline: float,
        supervisor: SolverSupervisor | None = None,
        *,
        anytime_steps: int = 8,
        slack_time: float = 5.0,
        slack_energy: float = 1.0,
    ) -> None:
        if horizon <= 0 or deadline <= 0:
            raise ValueError("horizon and deadline must be positive")
        self.instance = instance
        self.horizon = horizon
        self.uncertainty = uncertainty
        self.policy = policy
        self.deadline = deadline
        self.supervisor = supervisor or SolverSupervisor()
        self.anytime_steps = anytime_steps
        self.slack_time = slack_time
        self.slack_energy = slack_energy
        self.backup = BackupStore()
        self.last_record: dict = {}

    def close(self) -> None:
        self.supervisor.close()

    def propose(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        state = observation_version(observation, self.uncertainty)
        choice = classify(
            self.policy,
            trigger,
            self.backup.certificate,
            slack_time=self.slack_time,
            slack_energy=self.slack_energy,
        )
        if _pending(observation) and not choice.optimize:
            choice = TriggerDecision(True, "pending_announcement", True)
        record = {
            "observation_time": observation.time,
            "action_id": state,
            "accepted_commitments": len(observation.accepted),
            "backup_version": self.backup.version,
            "optimize": choice.optimize,
            "trigger_reason": choice.reason,
            "safety_related": choice.safety_related,
            "deadline": self.deadline,
            "examined": 0,
            "rejected_by_certificate": 0,
            "accepted_candidates": 0,
            "objective_note": "",
            "optimize_seconds": 0.0,
            "validation_seconds": 0.0,
            "timeout": False,
            "fallback": False,
            "replaced_backup": False,
            "selected_action": {},
            "certificate_verdict": None if self.backup.certificate is None else self.backup.certificate.verdict.value,
            "violation": False,
        }
        if not choice.optimize:
            decision = self._from_backup(observation, trigger, record, started, fallback=False)
            record["objective_note"] = "kept certified backup without reoptimization"
            self.last_record = record
            decision.audit = record
            return decision
        allowed = frozenset(observation.released_open) | frozenset(observation.accepted) | frozenset(
            observation.in_service
        ) | frozenset(observation.completed)
        payload = {
            "op": "improve",
            "instance": self.instance,
            "observation": observation,
            "incumbent": {vid: list(visits) for vid, visits in self.backup.routes.items()},
            "uncertainty": self.uncertainty,
            "steps": self.anytime_steps,
            "horizon": self.horizon,
            # Hidden future releases are not listed. The network tables remain static.
            "allowed_customers": allowed,
        }
        validation_time = 0.0
        rejected = 0
        accepted_n = 0

        def validate(candidate: dict):
            nonlocal validation_time, rejected, accepted_n
            t0 = perf_counter()
            if candidate.get("commitment_failed"):
                rejected += 1
                validation_time += perf_counter() - t0
                return None
            if not candidate.get("certificate_ok"):
                rejected += 1
                validation_time += perf_counter() - t0
                return None
            newly = tuple(candidate.get("newly_accepted", []))
            required = tuple(observation.accepted) + newly
            certificate = certify_routes(
                self.instance,
                observation,
                candidate["routes"],
                self.uncertainty,
                required=required,
            )
            validation_time += perf_counter() - t0
            if certificate.verdict is not Verdict.CERTIFIED_FEASIBLE:
                rejected += 1
                return None
            accepted_n += 1
            return certificate

        result = self.supervisor.run(payload, self.deadline, state, validate)
        record["examined"] = result.messages
        record["rejected_by_certificate"] = rejected
        record["accepted_candidates"] = accepted_n
        record["optimize_seconds"] = result.elapsed
        record["validation_seconds"] = validation_time
        record["timeout"] = result.status in {"timeout", "partial"}
        record["solver_status"] = result.status
        if result.status in {"timeout", "crash", "error"} or result.accepted_message is None:
            record["fallback"] = True
            if result.status == "crash":
                record["objective_note"] = result.error or "solver crash"
            elif result.status == "error":
                record["objective_note"] = result.error or "solver error"
            else:
                record["objective_note"] = "deadline expired before a validated candidate"
            decision = self._from_backup(observation, trigger, record, started, fallback=True)
            self.last_record = record
            decision.audit = record
            return decision
        candidate = result.accepted_message["candidate"]
        certificate: Certificate = result.accepted_message["validation"]
        staged = self.backup.stage(candidate["routes"], certificate, state)
        record["replaced_backup"] = staged
        record["objective_note"] = "staged certified candidate"
        record["certificate_verdict"] = certificate.verdict.value
        decision = self._decision_from_routes(
            observation,
            trigger,
            candidate["routes"],
            list(candidate.get("newly_accepted", [])),
            list(candidate.get("rejected", [])),
            fallback=False,
            no_continuation=False,
            started=started,
            notes=[choice.reason, result.status],
        )
        record["selected_action"] = {
            vid: [visit.node_id + ":" + visit.purpose for visit in visits[:1]]
            for vid, visits in candidate["routes"].items()
        }
        self.last_record = record
        decision.audit = record
        return decision

    def commit(self, observation: Observation) -> bool:
        return self.backup.commit(observation_version(observation, self.uncertainty))

    def discard(self) -> None:
        self.backup.discard()

    def holds(self, observation: Observation) -> bool:
        routes = self.backup._staged_routes if self.backup._staged_routes is not None else self.backup.routes
        if not routes and not observation.accepted:
            certificate = certify_routes(
                self.instance,
                observation,
                {v.id: [] for v in observation.vehicles},
                self.uncertainty,
            )
            return certificate.verdict is Verdict.CERTIFIED_FEASIBLE
        certificate = certify_routes(self.instance, observation, routes, self.uncertainty)
        return certificate.verdict is Verdict.CERTIFIED_FEASIBLE

    def fallback_decision(self, observation: Observation, trigger: str) -> Decision:
        self.discard()
        record = dict(self.last_record)
        record["fallback"] = True
        record["replaced_backup"] = False
        record["trigger_reason"] = trigger
        decision = self._from_backup(observation, trigger, record, perf_counter(), fallback=True)
        decision.audit = record
        self.last_record = record
        return decision

    def _from_backup(
        self,
        observation: Observation,
        trigger: str,
        record: dict,
        started: float,
        *,
        fallback: bool,
    ) -> Decision:
        if self.backup.certified:
            routes = {
                vehicle.id: dispatch_suffix(
                    self.backup.routes.get(vehicle.id, []),
                    observation,
                    vehicle.anchor.node,
                    vehicle.anchor.soc,
                    self.instance.vehicle_type.battery_capacity,
                )
                for vehicle in observation.vehicles
            }
            certificate = certify_routes(self.instance, observation, routes, self.uncertainty)
            if certificate.verdict is not Verdict.CERTIFIED_FEASIBLE:
                routes = {vehicle.id: [] for vehicle in observation.vehicles}
                no_continuation = True
                record["certificate_verdict"] = certificate.verdict.value
                record["violation"] = bool(observation.accepted)
            else:
                no_continuation = False
                record["certificate_verdict"] = certificate.verdict.value
        else:
            certificate = certify_routes(
                self.instance,
                observation,
                {vehicle.id: [] for vehicle in observation.vehicles},
                self.uncertainty,
                required=tuple(observation.accepted),
            )
            routes = {vehicle.id: [] for vehicle in observation.vehicles}
            no_continuation = certificate.verdict is not Verdict.CERTIFIED_FEASIBLE
            record["certificate_verdict"] = certificate.verdict.value
            record["violation"] = no_continuation and bool(observation.accepted)
        record["selected_action"] = {
            vid: [visit.node_id + ":" + visit.purpose for visit in visits[:1]] for vid, visits in routes.items()
        }
        if not record.get("optimize_seconds"):
            record["optimize_seconds"] = perf_counter() - started
        return self._decision_from_routes(
            observation,
            trigger,
            routes,
            [],
            [],
            fallback=fallback or not self.backup.certified,
            no_continuation=no_continuation,
            started=started,
            notes=[str(record.get("trigger_reason", trigger))],
        )

    def _decision_from_routes(
        self,
        observation: Observation,
        trigger: str,
        routes: dict[str, list[Visit]],
        newly: list[str],
        rejected: list[str],
        *,
        fallback: bool,
        no_continuation: bool,
        started: float,
        notes: list[str],
    ) -> Decision:
        accepted = list(observation.accepted) + [cid for cid in newly if cid not in observation.accepted]
        planned = [visit.node_id for visits in routes.values() for visit in visits if visit.purpose == "service"]
        protected = set(observation.completed) | set(observation.in_service) | set(planned) | set(accepted)
        for vehicle in observation.vehicles:
            protected.update(vehicle.onboard)
            if vehicle.locked_destination:
                protected.add(vehicle.locked_destination)
        clean_rejected = [cid for cid in rejected if cid not in protected]
        locked = {vehicle.id: vehicle.locked_destination for vehicle in observation.vehicles}
        return Decision(
            time=observation.time,
            routes={vid: list(visits) for vid, visits in routes.items()},
            accepted=accepted,
            newly_accepted=list(newly),
            rejected=clean_rejected,
            deferred=[],
            fallback_used=fallback,
            no_feasible_continuation=no_continuation,
            horizon_extended=True,
            planned_service=planned,
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=perf_counter() - started,
            trigger=trigger,
            locked_destinations=locked,
            notes=notes,
        )
