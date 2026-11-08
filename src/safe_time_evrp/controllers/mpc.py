"""Deterministic event-triggered MPC baseline for dynamic EVRP.

At a decision epoch the controller sees only an Observation. It builds a route
suffix for every vehicle from that vehicle's anchor (the predicted end of any
noninterruptible action). The episode runner executes the first idle action and
leaves the rest as a provisional suffix.

A previous feasible suffix is reused when a new construction cannot cover accepted
commitments. That fallback is a heuristic incumbent, not a recursive-feasibility proof.
If the incumbent is also infeasible, idle vehicles are sent to the depot when that
return itself satisfies the battery and depot deadline. This is recorded as
``no_feasible_continuation``.
"""

from __future__ import annotations

from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.optimization.insertion import construct_routes


class EventTriggeredMPC:
    def __init__(
        self,
        instance: Instance,
        horizon: float,
        energy: NominalLinearEnergy | None = None,
    ) -> None:
        if horizon <= 0:
            raise ValueError("planning horizon must be positive")
        self._full_instance = instance
        # Back-compat attribute: may be a public snapshot during decide()
        self.instance = instance
        self.horizon = horizon
        self.energy = energy or NominalLinearEnergy()
        self.previous_routes: dict[str, list[Visit]] | None = None

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full_instance, observation, self.horizon)
        public = snapshot.instance
        plan = construct_routes(
            public,
            observation,
            horizon=self.horizon,
            energy=self.energy,
        )
        notes = list(plan.notes)
        routes = plan.routes
        fallback = False
        no_continuation = False
        newly_accepted = list(plan.newly_accepted)
        rejected = list(plan.rejected)
        planned = list(plan.planned_service)
        distance = plan.total_distance
        charge_time = plan.total_charge_time
        if plan.feasible_commitments:
            self.previous_routes = {vid: list(visits) for vid, visits in routes.items()}
        elif self._incumbent_covers(observation):
            assert self.previous_routes is not None
            routes = {vid: list(visits) for vid, visits in self.previous_routes.items()}
            fallback = True
            newly_accepted = []
            rejected = []
            planned, distance, charge_time = self._metrics(observation, routes)
            notes.append("fallback_previous_feasible_suffix")
        else:
            no_continuation = True
            routes = self._safe_returns(observation)
            newly_accepted = []
            rejected = []
            planned, distance, charge_time = self._metrics(observation, routes)
            notes.append("no_feasible_continuation")
            notes.append("safe_return_is_a_heuristic_backup_not_a_certificate")
        elapsed = perf_counter() - started
        locked = {vehicle.id: vehicle.locked_destination for vehicle in observation.vehicles}
        return Decision(
            time=observation.time,
            routes=routes,
            accepted=list(plan.accepted) if plan.feasible_commitments else list(observation.accepted),
            newly_accepted=newly_accepted,
            rejected=rejected,
            deferred=list(plan.deferred),
            fallback_used=fallback,
            no_feasible_continuation=no_continuation,
            horizon_extended=plan.horizon_extended,
            planned_service=planned,
            total_distance=distance,
            total_charge_time=charge_time,
            optimize_seconds=elapsed,
            trigger=trigger,
            locked_destinations=locked,
            notes=notes,
        )

    def _public(self, observation: Observation) -> Instance:
        return make_public_snapshot(self._full_instance, observation, self.horizon).instance

    def _incumbent_covers(self, observation: Observation) -> bool:
        if not self.previous_routes:
            return False
        public = self._public(observation)
        pending = set(observation.accepted)
        served: set[str] = set()
        for vehicle in observation.vehicles:
            visits = self.previous_routes.get(vehicle.id, [])
            result = evaluate_route(public, vehicle.anchor, visits, self.energy)
            if not result.feasible:
                return False
            served.update(result.served)
        return pending <= served

    def _safe_returns(self, observation: Observation) -> dict[str, list[Visit]]:
        public = self._public(observation)
        routes: dict[str, list[Visit]] = {}
        for vehicle in observation.vehicles:
            if vehicle.status in {"traveling", "serving", "charging"}:
                routes[vehicle.id] = list((self.previous_routes or {}).get(vehicle.id, []))
                continue
            candidate = [Visit(public.depot_id, "return")]
            result = evaluate_route(public, vehicle.anchor, candidate, self.energy)
            routes[vehicle.id] = result.visits if result.feasible else []
        return routes

    def _metrics(
        self,
        observation: Observation,
        routes: dict[str, list[Visit]],
    ) -> tuple[list[str], float, float]:
        public = self._public(observation)
        served: list[str] = []
        distance = 0.0
        charge_time = 0.0
        for vehicle in observation.vehicles:
            result = evaluate_route(
                public,
                vehicle.anchor,
                routes.get(vehicle.id, []),
                self.energy,
            )
            if not result.feasible:
                continue
            served.extend(result.served)
            distance += result.distance
            charge_time += result.charge_time
        return sorted(set(served)), distance, charge_time
