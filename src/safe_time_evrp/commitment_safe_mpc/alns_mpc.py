"""Reactive ALNS–MPC baseline (B0) on the authoritative FleetSimulator plant.

Uses Adaptive Large Neighborhood Search over multi-vehicle customer sequences,
decoded with SAFE ``evaluate_route`` / charge-aware insertion variants.

Not a robust-safety certificate: validation is under nominal physics only.
New customers enter ``newly_accepted`` only after a verified continuation covers
them together with all existing accepted commitments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil
from random import Random
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.optimization.insertion import _variants, construct_routes

DESTROY_OPS = ("random", "worst_distance", "related", "critical_tw")
REPAIR_OPS = ("regret2", "regret3", "greedy")


@dataclass
class ALNSDiagnostics:
    iterations: int = 0
    candidates_evaluated: int = 0
    improvements: int = 0
    rejected_moves: int = 0
    route_evaluations: int = 0
    destroy_counts: dict[str, int] = field(default_factory=dict)
    repair_counts: dict[str, int] = field(default_factory=dict)
    first_feasible_seconds: float | None = None
    best_feasible_seconds: float | None = None
    constructor_distance: float | None = None
    best_distance: float | None = None
    improved_over_constructor: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class _FleetSolution:
    sequences: dict[str, list[str]]
    routes: dict[str, list[Visit]]
    distance: float
    charge_time: float
    served: list[str]
    newly_accepted: list[str]
    rejected: list[str]
    deferred: list[str]
    accepted: list[str]
    feasible_commitments: bool
    notes: list[str] = field(default_factory=list)


def _customers_in_routes(routes: dict[str, list[Visit]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for vid, visits in routes.items():
        out[vid] = [v.node_id for v in visits if v.purpose == "service"]
    return out


def _decode_sequences(
    instance: Instance,
    observation: Observation,
    sequences: dict[str, list[str]],
    energy: NominalLinearEnergy,
    diag: ALNSDiagnostics,
) -> tuple[dict[str, list[Visit]], float, float, list[str]] | None:
    """Decode fixed customer sequences with charge/reload variants via evaluate_route."""
    routes: dict[str, list[Visit]] = {v.id: [] for v in observation.vehicles}
    total_d = 0.0
    total_c = 0.0
    served: list[str] = []
    stations = instance.charger_ids()
    for vehicle in observation.vehicles:
        seq = sequences.get(vehicle.id, [])
        route: list[Visit] = []
        for customer_id in seq:
            placed = False
            best = None
            best_key = None
            for pos in range(len(route) + 1):
                for candidate in _variants(route, pos, customer_id, stations, instance.depot_id):
                    diag.route_evaluations += 1
                    result = evaluate_route(instance, vehicle.anchor, candidate, energy)
                    if not result.feasible or customer_id not in result.served:
                        continue
                    key = (result.distance, result.charge_time, pos)
                    if best_key is None or key < best_key:
                        best_key = key
                        best = result.visits[:-1]
                        placed = True
            if not placed:
                return None
            assert best is not None
            route = best
        diag.route_evaluations += 1
        final = evaluate_route(instance, vehicle.anchor, route, energy)
        if not final.feasible:
            return None
        routes[vehicle.id] = final.visits
        total_d += final.distance
        total_c += final.charge_time
        served.extend(final.served)
    return routes, total_d, total_c, served


def _score(distance: float, charge_time: float, served: int) -> tuple[float, float, int]:
    # Lexicographic: more served is better (negated), then distance, then charge
    return (-served, distance, charge_time)


class ReactiveAlnsMpc:
    """B0: reactive ALNS–MPC with public-snapshot information boundary."""

    def __init__(
        self,
        instance: Instance,
        horizon: float,
        *,
        energy: NominalLinearEnergy | None = None,
        iterations: int = 40,
        destroy_fraction: float = 0.35,
        reaction_factor: float = 0.25,
        segment_length: int = 8,
        time_limit_seconds: float = 0.25,
        seed: int = 0,
    ) -> None:
        if horizon <= 0:
            raise ValueError("planning horizon must be positive")
        if iterations < 1:
            raise ValueError("ALNS iterations must be positive")
        self._full_instance = instance
        self.horizon = horizon
        self.energy = energy or NominalLinearEnergy()
        self.iterations = iterations
        self.destroy_fraction = destroy_fraction
        self.reaction_factor = reaction_factor
        self.segment_length = segment_length
        self.time_limit_seconds = time_limit_seconds
        self.rng = Random(seed)
        self.previous_routes: dict[str, list[Visit]] | None = None
        self.last_diagnostics = ALNSDiagnostics()

    def decide(self, observation: Observation, trigger: str) -> Decision:
        started = perf_counter()
        snapshot = make_public_snapshot(self._full_instance, observation, self.horizon)
        public = snapshot.instance
        diag = ALNSDiagnostics()
        self.last_diagnostics = diag

        seed_plan = construct_routes(public, observation, horizon=self.horizon, energy=self.energy)
        incumbent = self._from_insertion(seed_plan, observation, public, diag)
        if incumbent is not None and incumbent.feasible_commitments:
            diag.first_feasible_seconds = perf_counter() - started
            diag.best_feasible_seconds = diag.first_feasible_seconds
            diag.constructor_distance = incumbent.distance
            diag.best_distance = incumbent.distance
        else:
            # Try previous suffix as incumbent if it still covers commitments
            recovered = self._recover_incumbent(observation, public, diag)
            if recovered is not None:
                incumbent = recovered
                diag.first_feasible_seconds = perf_counter() - started
                diag.best_feasible_seconds = diag.first_feasible_seconds
                diag.notes.append("recovered_previous_suffix")
            else:
                diag.notes.append("no_feasible_incumbent_after_constructor")

        if incumbent is not None and incumbent.feasible_commitments:
            destroy_w = {name: 1.0 for name in DESTROY_OPS}
            repair_w = {name: 1.0 for name in REPAIR_OPS}
            destroy_reward = {name: 0.0 for name in DESTROY_OPS}
            repair_reward = {name: 0.0 for name in REPAIR_OPS}
            destroy_count = {name: 0 for name in DESTROY_OPS}
            repair_count = {name: 0 for name in REPAIR_OPS}
            current = incumbent
            for it in range(self.iterations):
                if perf_counter() - started >= self.time_limit_seconds:
                    diag.notes.append("time_limit")
                    break
                diag.iterations += 1
                d_op = self._roulette(DESTROY_OPS, destroy_w)
                r_op = self._roulette(REPAIR_OPS, repair_w)
                destroy_count[d_op] += 1
                repair_count[r_op] += 1
                diag.destroy_counts[d_op] = destroy_count[d_op]
                diag.repair_counts[r_op] = repair_count[r_op]

                trial_seq, removed = self._destroy(current.sequences, observation, public, d_op)
                if not removed:
                    diag.rejected_moves += 1
                    continue
                trial_seq = self._repair(trial_seq, removed, observation, public, r_op, current.accepted, diag)
                decoded = _decode_sequences(public, observation, trial_seq, self.energy, diag)
                diag.candidates_evaluated += 1
                if decoded is None:
                    diag.rejected_moves += 1
                    reward = 0.0
                else:
                    routes, dist, charge, served = decoded
                    if not self._covers_commitments(observation, served):
                        diag.rejected_moves += 1
                        reward = 0.0
                    else:
                        newly, rejected, deferred, accepted = self._acceptance_sets(
                            observation, public, served, seed_plan.deferred
                        )
                        # Only accept news that appear in the verified served set
                        cand = _FleetSolution(
                            sequences=trial_seq,
                            routes=routes,
                            distance=dist,
                            charge_time=charge,
                            served=served,
                            newly_accepted=newly,
                            rejected=rejected,
                            deferred=deferred,
                            accepted=accepted,
                            feasible_commitments=True,
                        )
                        cur_score = _score(current.distance, current.charge_time, len(current.served))
                        new_score = _score(cand.distance, cand.charge_time, len(cand.served))
                        if new_score < cur_score:
                            current = cand
                            diag.improvements += 1
                            diag.best_feasible_seconds = perf_counter() - started
                            diag.best_distance = cand.distance
                            reward = (
                                5.0
                                if new_score < _score(incumbent.distance, incumbent.charge_time, len(incumbent.served))
                                else 2.0
                            )
                            if new_score < _score(incumbent.distance, incumbent.charge_time, len(incumbent.served)):
                                incumbent = cand
                        else:
                            # Accept equal-or-worse with small probability (SA-like)
                            if self.rng.random() < 0.05:
                                current = cand
                                reward = 1.0
                            else:
                                diag.rejected_moves += 1
                                reward = 0.5
                destroy_reward[d_op] += reward
                repair_reward[r_op] += reward
                if (it + 1) % self.segment_length == 0:
                    self._adapt(destroy_w, destroy_reward, destroy_count)
                    self._adapt(repair_w, repair_reward, repair_count)
                    destroy_reward = {name: 0.0 for name in DESTROY_OPS}
                    repair_reward = {name: 0.0 for name in REPAIR_OPS}
                    destroy_count = {name: 0 for name in DESTROY_OPS}
                    repair_count = {name: 0 for name in REPAIR_OPS}

            if diag.constructor_distance is not None and diag.best_distance is not None:
                diag.improved_over_constructor = diag.best_distance + 1e-9 < diag.constructor_distance

        elapsed = perf_counter() - started
        if incumbent is None or not incumbent.feasible_commitments:
            routes = self._safe_returns(observation)
            return Decision(
                time=observation.time,
                routes=routes,
                accepted=list(observation.accepted),
                newly_accepted=[],
                rejected=[],
                deferred=[],
                fallback_used=False,
                no_feasible_continuation=True,
                horizon_extended=False,
                planned_service=[],
                total_distance=0.0,
                total_charge_time=0.0,
                optimize_seconds=elapsed,
                trigger=trigger,
                locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
                notes=["alns_no_feasible_continuation", *diag.notes],
                audit={"alns": diag.__dict__},
            )

        self.previous_routes = {vid: list(vs) for vid, vs in incumbent.routes.items()}
        return Decision(
            time=observation.time,
            routes=incumbent.routes,
            accepted=incumbent.accepted,
            newly_accepted=incumbent.newly_accepted,
            rejected=incumbent.rejected,
            deferred=incumbent.deferred,
            fallback_used=False,
            no_feasible_continuation=False,
            horizon_extended=False,
            planned_service=sorted(incumbent.served),
            total_distance=incumbent.distance,
            total_charge_time=incumbent.charge_time,
            optimize_seconds=elapsed,
            trigger=trigger,
            locked_destinations={v.id: v.locked_destination for v in observation.vehicles},
            notes=[
                "reactive_alns_mpc",
                f"iterations={diag.iterations}",
                f"improvements={diag.improvements}",
                f"improved_over_constructor={diag.improved_over_constructor}",
                *diag.notes[:4],
            ],
            audit={
                "alns": {
                    "iterations": diag.iterations,
                    "candidates_evaluated": diag.candidates_evaluated,
                    "improvements": diag.improvements,
                    "rejected_moves": diag.rejected_moves,
                    "route_evaluations": diag.route_evaluations,
                    "constructor_distance": diag.constructor_distance,
                    "best_distance": diag.best_distance,
                    "improved_over_constructor": diag.improved_over_constructor,
                    "first_feasible_seconds": diag.first_feasible_seconds,
                    "best_feasible_seconds": diag.best_feasible_seconds,
                }
            },
        )

    def _from_insertion(
        self,
        plan,
        observation: Observation,
        public: Instance,
        diag: ALNSDiagnostics,
    ) -> _FleetSolution | None:
        if not plan.feasible_commitments:
            return None
        # Re-validate: every newly_accepted must appear in served under evaluate_route
        served: list[str] = []
        distance = 0.0
        charge = 0.0
        routes: dict[str, list[Visit]] = {}
        for vehicle in observation.vehicles:
            visits = plan.routes.get(vehicle.id, [])
            diag.route_evaluations += 1
            result = evaluate_route(public, vehicle.anchor, visits, self.energy)
            if not result.feasible:
                return None
            routes[vehicle.id] = result.visits
            served.extend(result.served)
            distance += result.distance
            charge += result.charge_time
        if not self._covers_commitments(observation, served):
            return None
        newly = [c for c in plan.newly_accepted if c in served]
        rejected = [c for c in plan.rejected if c not in newly]
        accepted = list(observation.accepted)
        for c in newly:
            if c not in accepted:
                accepted.append(c)
        return _FleetSolution(
            sequences=_customers_in_routes(routes),
            routes=routes,
            distance=distance,
            charge_time=charge,
            served=served,
            newly_accepted=newly,
            rejected=rejected,
            deferred=list(plan.deferred),
            accepted=accepted,
            feasible_commitments=True,
            notes=list(plan.notes),
        )

    def _recover_incumbent(
        self, observation: Observation, public: Instance, diag: ALNSDiagnostics
    ) -> _FleetSolution | None:
        if not self.previous_routes:
            return None
        routes: dict[str, list[Visit]] = {}
        served: list[str] = []
        distance = 0.0
        charge = 0.0
        for vehicle in observation.vehicles:
            visits = self.previous_routes.get(vehicle.id, [])
            diag.route_evaluations += 1
            result = evaluate_route(public, vehicle.anchor, visits, self.energy)
            if not result.feasible:
                return None
            routes[vehicle.id] = result.visits
            served.extend(result.served)
            distance += result.distance
            charge += result.charge_time
        if not self._covers_commitments(observation, served):
            return None
        return _FleetSolution(
            sequences=_customers_in_routes(routes),
            routes=routes,
            distance=distance,
            charge_time=charge,
            served=served,
            newly_accepted=[],
            rejected=[],
            deferred=[],
            accepted=list(observation.accepted),
            feasible_commitments=True,
            notes=["previous_suffix"],
        )

    def _covers_commitments(self, observation: Observation, served: list[str]) -> bool:
        pending = set(observation.accepted) - set(observation.completed) - set(observation.in_service)
        return pending.issubset(set(served) | set(observation.in_service))

    def _acceptance_sets(
        self,
        observation: Observation,
        public: Instance,
        served: list[str],
        deferred_seed: list[str],
    ) -> tuple[list[str], list[str], list[str], list[str]]:
        served_set = set(served)
        pending_commit = set(observation.accepted) - set(observation.completed) - set(observation.in_service)
        newly = []
        rejected = []
        for cid in observation.released_open:
            if cid in pending_commit or cid in observation.completed or cid in observation.in_service:
                continue
            if cid in deferred_seed:
                continue
            if cid in served_set:
                newly.append(cid)
            else:
                rejected.append(cid)
        accepted = list(observation.accepted)
        for c in newly:
            if c not in accepted:
                accepted.append(c)
        return newly, rejected, list(deferred_seed), accepted

    def _destroy(
        self,
        sequences: dict[str, list[str]],
        observation: Observation,
        public: Instance,
        op: str,
    ) -> tuple[dict[str, list[str]], list[tuple[str, str]]]:
        owned: list[tuple[str, int, str]] = [
            (vid, pos, cid) for vid, seq in sequences.items() for pos, cid in enumerate(seq)
        ]
        # Never destroy customers already onboard / locked (noninterruptible)
        locked_customers: set[str] = set()
        for vehicle in observation.vehicles:
            locked_customers |= set(vehicle.anchor.onboard)
            if vehicle.locked_destination:
                locked_customers.add(vehicle.locked_destination)
        removable = [row for row in owned if row[2] not in locked_customers]
        if not removable:
            return {k: list(v) for k, v in sequences.items()}, []
        k = max(1, min(len(removable), ceil(self.destroy_fraction * len(removable))))
        if op == "random":
            self.rng.shuffle(removable)
            chosen = removable[:k]
        elif op == "critical_tw":
            chosen = sorted(
                removable, key=lambda row: public.node(row[2]).window.due - public.node(row[2]).window.ready
            )[:k]
        elif op == "related":
            anchor = public.node(self.rng.choice(removable)[2])
            chosen = sorted(
                removable,
                key=lambda row: (
                    (public.node(row[2]).x - anchor.x) ** 2 + (public.node(row[2]).y - anchor.y) ** 2,
                    abs(public.node(row[2]).window.due - anchor.window.due),
                ),
            )[:k]
        else:  # worst_distance proxy: later due first (harder) as crude worst
            chosen = sorted(removable, key=lambda row: -public.node(row[2]).window.due)[:k]

        remove_set = {(vid, cid) for vid, _, cid in chosen}
        new_seq = {vid: [cid for cid in seq if (vid, cid) not in remove_set] for vid, seq in sequences.items()}
        removed = [(vid, cid) for vid, _, cid in chosen]
        return new_seq, removed

    def _repair(
        self,
        sequences: dict[str, list[str]],
        removed: list[tuple[str, str]],
        observation: Observation,
        public: Instance,
        op: str,
        accepted: list[str],
        diag: ALNSDiagnostics,
    ) -> dict[str, list[str]]:
        # Priority: accepted commitments first
        pending_commit = set(accepted) - set(observation.completed) - set(observation.in_service)
        pool = [cid for _, cid in removed]
        pool = sorted(set(pool), key=lambda cid: (0 if cid in pending_commit else 1, public.node(cid).window.due, cid))
        seq = {vid: list(s) for vid, s in sequences.items()}
        for customer_id in pool:
            options: list[tuple[float, float, str, int]] = []
            for vehicle in observation.vehicles:
                base = seq[vehicle.id]
                for pos in range(len(base) + 1):
                    trial = {v: list(s) for v, s in seq.items()}
                    trial[vehicle.id] = base[:pos] + [customer_id] + base[pos:]
                    decoded = _decode_sequences(public, observation, trial, self.energy, diag)
                    if decoded is None:
                        continue
                    _routes, dist, charge, served = decoded
                    if customer_id not in served:
                        continue
                    options.append((dist, charge, vehicle.id, pos))
            if not options:
                continue
            options.sort()
            if op == "greedy":
                pick = options[0]
            elif op == "regret2":
                if len(options) == 1:
                    pick = options[0]
                else:
                    # maximize gap between best and second
                    regret = sorted(
                        ((options[min(1, len(options) - 1)][0] - options[0][0], options[0]) for _ in [0]),
                        reverse=True,
                    )
                    # standard: choose customer with max regret — here single customer, pick best
                    pick = options[0]
                    del regret
            else:  # regret3 → still insert at best position (customer already chosen)
                pick = options[0]
            _d, _c, vid, pos = pick
            seq[vid] = seq[vid][:pos] + [customer_id] + seq[vid][pos:]
        return seq

    def _roulette(self, names: tuple[str, ...], weights: dict[str, float]) -> str:
        total = sum(weights[n] for n in names)
        draw = self.rng.random() * total
        for name in names:
            draw -= weights[name]
            if draw <= 0:
                return name
        return names[-1]

    def _adapt(self, weights: dict[str, float], rewards: dict[str, float], counts: dict[str, int]) -> None:
        rho = self.reaction_factor
        for name in weights:
            if counts[name] <= 0:
                continue
            score = rewards[name] / counts[name]
            weights[name] = max(0.05, (1.0 - rho) * weights[name] + rho * score)

    def _safe_returns(self, observation: Observation) -> dict[str, list[Visit]]:
        depot = self._full_instance.depot_id
        out: dict[str, list[Visit]] = {}
        for vehicle in observation.vehicles:
            if vehicle.locked_destination is not None:
                out[vehicle.id] = []
            elif vehicle.node != depot:
                out[vehicle.id] = [Visit(depot, "return")]
            else:
                out[vehicle.id] = []
        return out
