"""Deterministic event-driven EVRP simulator.

Travel, service, and charging, once dispatched, run to completion. Waiting for a
time window is interruptible. Charging stations have no endogenous queue: the
Schneider benchmark does not define a station capacity.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import (
    Anchor,
    Decision,
    LogRecord,
    Observation,
    RequestStatus,
    VehicleStatus,
    VehicleView,
    Visit,
)


class SimulatorError(RuntimeError):
    pass


@dataclass
class _Vehicle:
    id: str
    node: str
    soc: float
    load: float
    onboard: set[str]
    status: VehicleStatus = VehicleStatus.IDLE
    suffix: list[Visit] = field(default_factory=list)
    action: dict | None = None
    anchor_after: Anchor | None = None
    locked_destination: str | None = None
    wait_customer: str | None = None


@dataclass(order=True)
class _Event:
    time: float
    priority: int
    seq: int
    kind: str = field(compare=False)
    vehicle_id: str | None = field(compare=False, default=None)
    payload: dict = field(compare=False, default_factory=dict)
    event_id: int = field(compare=False, default=0)
    cancelled: bool = field(compare=False, default=False)


class FleetSimulator:
    def __init__(
        self,
        instance: Instance,
        fleet_size: int,
        energy: NominalLinearEnergy | None = None,
    ) -> None:
        if fleet_size < 1:
            raise SimulatorError("fleet size must be positive")
        self.instance = instance
        self.energy = energy or NominalLinearEnergy()
        self.time = 0.0
        self.vehicles = {
            f"v{i + 1}": _Vehicle(
                id=f"v{i + 1}",
                node=instance.depot_id,
                soc=instance.vehicle_type.battery_capacity,
                load=0.0,
                onboard=set(),
            )
            for i in range(fleet_size)
        }
        self.requests: dict[str, RequestStatus] = {node.id: RequestStatus.HIDDEN for node in instance.customers}
        self.release_time: dict[str, float] = {}
        self.log: list[LogRecord] = []
        self._heap: list[_Event] = []
        self._seq = 0
        self._event_ids = 0
        self._cancelled: set[int] = set()
        self._log_seq = 0
        for vehicle in self.vehicles.values():
            self._record(
                "vehicle_init",
                vehicle.id,
                {
                    "node": vehicle.node,
                    "soc": vehicle.soc,
                    "load": vehicle.load,
                },
            )

    def schedule_release(self, customer_id: str, time: float) -> None:
        if customer_id not in self.requests:
            raise SimulatorError(f"unknown customer {customer_id}")
        if time < -EPS:
            raise SimulatorError("release time is negative")
        self.release_time[customer_id] = time
        self._push(time, 1, "request_release", payload={"customer_id": customer_id})

    def schedule_replan(self, time: float) -> int:
        return self._push(time, 2, "replan_interval")

    def cancel(self, event_id: int) -> None:
        self._cancelled.add(event_id)

    def next_event_time(self) -> float | None:
        while self._heap and (self._heap[0].cancelled or self._heap[0].event_id in self._cancelled):
            heapq.heappop(self._heap)
        if not self._heap:
            return None
        return self._heap[0].time

    def pop_event(self) -> _Event | None:
        while self._heap:
            event = heapq.heappop(self._heap)
            if event.cancelled or event.event_id in self._cancelled:
                continue
            self.time = event.time
            self._apply(event)
            return event
        return None

    def observation(self) -> Observation:
        released_open: list[str] = []
        accepted: list[str] = []
        completed: list[str] = []
        rejected: list[str] = []
        in_service: list[str] = []
        deferred: list[str] = []
        for customer_id, status in sorted(self.requests.items()):
            if status is RequestStatus.HIDDEN:
                continue
            if status is RequestStatus.COMPLETED:
                completed.append(customer_id)
            elif status is RequestStatus.REJECTED:
                rejected.append(customer_id)
            elif status is RequestStatus.IN_SERVICE:
                in_service.append(customer_id)
                released_open.append(customer_id)
            elif status is RequestStatus.ACCEPTED:
                accepted.append(customer_id)
                released_open.append(customer_id)
            elif status is RequestStatus.DEFERRED:
                deferred.append(customer_id)
                released_open.append(customer_id)
            elif status is RequestStatus.ANNOUNCED:
                released_open.append(customer_id)
            elif status is RequestStatus.ACCEPTED_UNFULFILLED:
                accepted.append(customer_id)
                released_open.append(customer_id)
        views = tuple(self._view(vehicle) for vehicle in self.vehicles.values())
        return Observation(
            time=self.time,
            vehicles=views,
            released_open=tuple(released_open),
            accepted=tuple(accepted),
            completed=tuple(completed),
            rejected=tuple(rejected),
            in_service=tuple(in_service),
            deferred=tuple(deferred),
        )

    def apply_decision(self, decision: Decision) -> None:
        for customer_id in decision.newly_accepted:
            status = self.requests.get(customer_id)
            if status in {RequestStatus.ANNOUNCED, RequestStatus.DEFERRED}:
                self.requests[customer_id] = RequestStatus.ACCEPTED
        for customer_id in decision.deferred:
            if self.requests.get(customer_id) is RequestStatus.ANNOUNCED:
                self.requests[customer_id] = RequestStatus.DEFERRED
        for customer_id in decision.rejected:
            status = self.requests.get(customer_id)
            if status in {RequestStatus.ANNOUNCED, RequestStatus.DEFERRED}:
                self.requests[customer_id] = RequestStatus.REJECTED
        self._record(
            "decision",
            None,
            {
                "trigger": decision.trigger,
                "accepted": list(decision.accepted),
                "newly_accepted": list(decision.newly_accepted),
                "rejected": list(decision.rejected),
                "deferred": list(decision.deferred),
                "fallback_used": decision.fallback_used,
                "no_feasible_continuation": decision.no_feasible_continuation,
                "horizon_extended": decision.horizon_extended,
                "planned_service": list(decision.planned_service),
                "optimize_seconds": decision.optimize_seconds,
                "locked_destinations": dict(decision.locked_destinations),
                "routes": {
                    vid: [visit.node_id + ":" + visit.purpose for visit in visits]
                    for vid, visits in decision.routes.items()
                },
                "notes": list(decision.notes),
                "audit": dict(decision.audit or {}),
            },
        )
        for vehicle in self.vehicles.values():
            visits = decision.routes.get(vehicle.id, [])
            if vehicle.status in {
                VehicleStatus.TRAVELING,
                VehicleStatus.SERVING,
                VehicleStatus.CHARGING,
            }:
                vehicle.suffix = list(visits)
                continue
            if vehicle.status is VehicleStatus.WAITING:
                if vehicle.action and "event_id" in vehicle.action:
                    self.cancel(vehicle.action["event_id"])
                vehicle.status = VehicleStatus.IDLE
                vehicle.action = None
                vehicle.wait_customer = None
            self._start_suffix(vehicle, list(visits))

    def mark_finished(self) -> None:
        for customer_id, status in list(self.requests.items()):
            if status is RequestStatus.ACCEPTED:
                self.requests[customer_id] = RequestStatus.ACCEPTED_UNFULFILLED
        end_state = {
            vehicle.id: {
                "node": vehicle.node,
                "soc": vehicle.soc,
                "load": vehicle.load,
                "status": vehicle.status.value,
                "onboard": sorted(vehicle.onboard),
            }
            for vehicle in self.vehicles.values()
        }
        self._record("episode_end", None, {"vehicles": end_state, "time": self.time})

    def _start_suffix(self, vehicle: _Vehicle, visits: list[Visit]) -> None:
        vehicle.suffix = visits
        if not visits:
            vehicle.locked_destination = None
            return
        first = visits[0]
        if first.purpose == "return" and first.node_id == vehicle.node and len(visits) == 1:
            vehicle.suffix = []
            vehicle.locked_destination = None
            self._record(
                "depot_idle",
                vehicle.id,
                {"node": vehicle.node, "soc": vehicle.soc, "load": vehicle.load},
            )
            return
        if first.node_id != vehicle.node:
            self._load_tour(vehicle, visits)
            self._start_travel(vehicle, first.node_id)
            return
        if first.purpose == "service":
            vehicle.suffix = visits[1:]
            self._start_service(vehicle, first.node_id)
        elif first.purpose == "charge":
            vehicle.suffix = visits[1:]
            self._start_charge(vehicle, first)
        elif first.purpose == "reload":
            self._reload(vehicle, visits)
        elif first.purpose == "return":
            vehicle.suffix = visits[1:]
            self._start_suffix(vehicle, vehicle.suffix)
        else:
            raise SimulatorError(f"cannot start purpose {first.purpose}")

    def _load_tour(self, vehicle: _Vehicle, visits: list[Visit]) -> None:
        if vehicle.node != self.instance.depot_id:
            return
        ids: list[str] = []
        for visit in visits:
            if visit.purpose in {"reload", "return"}:
                break
            if visit.purpose == "service":
                ids.append(visit.node_id)
        extra = 0.0
        added: list[str] = []
        for customer_id in ids:
            if customer_id in vehicle.onboard:
                continue
            extra += self.instance.node(customer_id).demand
            added.append(customer_id)
        if vehicle.load + extra > self.instance.vehicle_type.load_capacity + EPS:
            raise SimulatorError("dispatch exceeds payload capacity")
        vehicle.load += extra
        vehicle.onboard.update(added)
        if added:
            self._record(
                "load_freight",
                vehicle.id,
                {
                    "node": vehicle.node,
                    "customers": added,
                    "load": vehicle.load,
                    "soc": vehicle.soc,
                },
            )

    def _start_travel(self, vehicle: _Vehicle, destination: str) -> None:
        arc = self.instance.arc(vehicle.node, destination)
        energy = self.energy.travel_energy(self.instance, arc, soc=vehicle.soc, load=vehicle.load)
        if vehicle.soc - energy < -EPS:
            raise SimulatorError(f"{vehicle.id} cannot travel {vehicle.node}->{destination}: battery")
        start_soc = vehicle.soc
        end_soc = start_soc - energy
        end_time = self.time + arc.travel_time
        vehicle.status = VehicleStatus.TRAVELING
        vehicle.locked_destination = destination
        event_id = self._push(
            end_time,
            0,
            "arrive",
            vehicle_id=vehicle.id,
            payload={
                "origin": vehicle.node,
                "destination": destination,
                "energy": energy,
                "travel_time": arc.travel_time,
                "soc_before": start_soc,
            },
        )
        vehicle.action = {"kind": "travel", "event_id": event_id, "destination": destination}
        vehicle.anchor_after = Anchor(
            node=destination,
            time=end_time,
            soc=end_soc,
            load=vehicle.load,
            onboard=frozenset(vehicle.onboard),
        )
        self._record(
            "depart",
            vehicle.id,
            {
                "origin": vehicle.node,
                "destination": destination,
                "soc": start_soc,
                "load": vehicle.load,
                "onboard": sorted(vehicle.onboard),
                "travel_time": arc.travel_time,
                "energy": energy,
            },
        )

    def _start_service(self, vehicle: _Vehicle, customer_id: str) -> None:
        node = self.instance.node(customer_id)
        if vehicle.node != customer_id:
            raise SimulatorError("service started away from the customer")
        if self.time > node.window.due + EPS:
            raise SimulatorError(f"service of {customer_id} misses the hard window")
        if customer_id not in vehicle.onboard:
            raise SimulatorError(f"goods for {customer_id} are not onboard")
        release = self.release_time.get(customer_id)
        if release is None or self.time + EPS < release:
            raise SimulatorError(f"service of {customer_id} before release")
        if self.time + EPS < node.window.ready:
            event_id = self._push(
                node.window.ready,
                0,
                "wait_end",
                vehicle_id=vehicle.id,
                payload={"customer_id": customer_id},
            )
            vehicle.status = VehicleStatus.WAITING
            vehicle.wait_customer = customer_id
            vehicle.locked_destination = None
            vehicle.action = {"kind": "wait", "event_id": event_id, "customer_id": customer_id}
            vehicle.anchor_after = None
            self._record(
                "wait_start",
                vehicle.id,
                {
                    "customer_id": customer_id,
                    "until": node.window.ready,
                    "soc": vehicle.soc,
                    "load": vehicle.load,
                    "node": vehicle.node,
                },
            )
            return
        end_time = self.time + node.service_time
        end_load = vehicle.load - node.demand
        event_id = self._push(
            end_time,
            0,
            "service_end",
            vehicle_id=vehicle.id,
            payload={"customer_id": customer_id, "demand": node.demand},
        )
        vehicle.status = VehicleStatus.SERVING
        vehicle.onboard.discard(customer_id)
        vehicle.load = end_load
        self.requests[customer_id] = RequestStatus.IN_SERVICE
        vehicle.action = {"kind": "service", "event_id": event_id, "customer_id": customer_id}
        vehicle.locked_destination = customer_id
        vehicle.anchor_after = Anchor(
            node=vehicle.node,
            time=end_time,
            soc=vehicle.soc,
            load=end_load,
            onboard=frozenset(vehicle.onboard),
        )
        self._record(
            "service_start",
            vehicle.id,
            {
                "customer_id": customer_id,
                "node": vehicle.node,
                "soc": vehicle.soc,
                "load": end_load,
                "service_time": node.service_time,
                "window_ready": node.window.ready,
                "window_due": node.window.due,
            },
        )

    def _start_charge(self, vehicle: _Vehicle, visit: Visit) -> None:
        station = self.instance.node(visit.node_id)
        if station.kind is not NodeKind.CHARGER or vehicle.node != visit.node_id:
            raise SimulatorError("charging started away from a charging station")
        policy = self.instance.vehicle_type.recharge_policy
        if policy == "full":
            target = self.instance.vehicle_type.battery_capacity
        else:
            if visit.charge_target is None:
                raise SimulatorError("partial charge is missing a target")
            target = visit.charge_target
        if target > self.instance.vehicle_type.battery_capacity + EPS or target < vehicle.soc - EPS:
            raise SimulatorError("impossible charge target")
        duration = self.energy.charge_duration(vehicle.soc, target, self.instance.vehicle_type.inverse_recharge_rate)
        if duration <= EPS:
            vehicle.soc = target
            self._record(
                "charge_skip",
                vehicle.id,
                {"station": visit.node_id, "soc": vehicle.soc, "reason": "already_at_target"},
            )
            self._start_suffix(vehicle, vehicle.suffix)
            return
        end_time = self.time + duration
        event_id = self._push(
            end_time,
            0,
            "charge_end",
            vehicle_id=vehicle.id,
            payload={"station": visit.node_id, "target": target, "soc_before": vehicle.soc},
        )
        vehicle.status = VehicleStatus.CHARGING
        vehicle.locked_destination = visit.node_id
        vehicle.action = {"kind": "charge", "event_id": event_id, "target": target}
        vehicle.anchor_after = Anchor(
            node=vehicle.node,
            time=end_time,
            soc=target,
            load=vehicle.load,
            onboard=frozenset(vehicle.onboard),
        )
        self._record(
            "charge_start",
            vehicle.id,
            {
                "station": visit.node_id,
                "soc": vehicle.soc,
                "target": target,
                "duration": duration,
                "load": vehicle.load,
                "node": vehicle.node,
            },
        )

    def _reload(self, vehicle: _Vehicle, visits: list[Visit]) -> None:
        if vehicle.node != self.instance.depot_id:
            raise SimulatorError("reload away from the depot")
        vehicle.load = 0.0
        vehicle.onboard.clear()
        self._record(
            "reload",
            vehicle.id,
            {"node": vehicle.node, "soc": vehicle.soc, "load": vehicle.load},
        )
        self._start_suffix(vehicle, visits[1:])

    def _apply(self, event: _Event) -> None:
        if event.kind == "request_release":
            customer_id = event.payload["customer_id"]
            if self.requests[customer_id] is RequestStatus.HIDDEN:
                self.requests[customer_id] = RequestStatus.ANNOUNCED
                self._record(
                    "request_release",
                    None,
                    {"customer_id": customer_id, "time": event.time},
                )
            return
        if event.kind == "replan_interval":
            self._record("replan_interval", None, {})
            return
        vehicle = self.vehicles[event.vehicle_id or ""]
        if event.kind == "arrive":
            origin = event.payload["origin"]
            destination = event.payload["destination"]
            energy = event.payload["energy"]
            if vehicle.node != origin or vehicle.status is not VehicleStatus.TRAVELING:
                raise SimulatorError("arrival does not match the traveling state")
            vehicle.soc -= energy
            if vehicle.soc < 0 and vehicle.soc >= -EPS:
                vehicle.soc = 0.0
            vehicle.node = destination
            vehicle.status = VehicleStatus.IDLE
            vehicle.action = None
            vehicle.locked_destination = None
            vehicle.anchor_after = None
            self._record(
                "arrive",
                vehicle.id,
                {
                    "origin": origin,
                    "destination": destination,
                    "energy": energy,
                    "travel_time": event.payload["travel_time"],
                    "soc_before": event.payload["soc_before"],
                    "soc": vehicle.soc,
                    "load": vehicle.load,
                    "node": vehicle.node,
                },
            )
            if destination == self.instance.depot_id:
                self._record(
                    "depot_arrival",
                    vehicle.id,
                    {"soc": vehicle.soc, "load": vehicle.load, "node": destination},
                )
            return
        if event.kind == "wait_end":
            if vehicle.status is not VehicleStatus.WAITING:
                return
            vehicle.status = VehicleStatus.IDLE
            vehicle.action = None
            vehicle.anchor_after = None
            self._record(
                "wait_end",
                vehicle.id,
                {
                    "customer_id": event.payload["customer_id"],
                    "node": vehicle.node,
                    "soc": vehicle.soc,
                    "load": vehicle.load,
                },
            )
            return
        if event.kind == "service_end":
            customer_id = event.payload["customer_id"]
            if vehicle.status is not VehicleStatus.SERVING:
                raise SimulatorError("service completion without an active service")
            vehicle.status = VehicleStatus.IDLE
            vehicle.action = None
            vehicle.locked_destination = None
            vehicle.anchor_after = None
            self.requests[customer_id] = RequestStatus.COMPLETED
            self._record(
                "service_end",
                vehicle.id,
                {
                    "customer_id": customer_id,
                    "node": vehicle.node,
                    "soc": vehicle.soc,
                    "load": vehicle.load,
                },
            )
            return
        if event.kind == "charge_end":
            if vehicle.status is not VehicleStatus.CHARGING:
                raise SimulatorError("charge completion without an active charge")
            vehicle.soc = event.payload["target"]
            vehicle.status = VehicleStatus.IDLE
            vehicle.action = None
            vehicle.locked_destination = None
            vehicle.anchor_after = None
            self._record(
                "charge_end",
                vehicle.id,
                {
                    "station": event.payload["station"],
                    "soc_before": event.payload["soc_before"],
                    "soc": vehicle.soc,
                    "target": event.payload["target"],
                    "load": vehicle.load,
                    "node": vehicle.node,
                },
            )
            return
        raise SimulatorError(f"unknown event {event.kind}")

    def _view(self, vehicle: _Vehicle) -> VehicleView:
        if vehicle.anchor_after is not None and vehicle.status in {
            VehicleStatus.TRAVELING,
            VehicleStatus.SERVING,
            VehicleStatus.CHARGING,
        }:
            anchor = vehicle.anchor_after
        else:
            anchor = Anchor(
                node=vehicle.node,
                time=self.time,
                soc=vehicle.soc,
                load=vehicle.load,
                onboard=frozenset(vehicle.onboard),
            )
        return VehicleView(
            id=vehicle.id,
            status=vehicle.status.value,
            node=vehicle.node,
            soc=vehicle.soc,
            load=vehicle.load,
            onboard=tuple(sorted(vehicle.onboard)),
            anchor=anchor,
            locked_destination=vehicle.locked_destination,
        )

    def _push(
        self,
        time: float,
        priority: int,
        kind: str,
        vehicle_id: str | None = None,
        payload: dict | None = None,
    ) -> int:
        self._seq += 1
        self._event_ids += 1
        event = _Event(
            time=time,
            priority=priority,
            seq=self._seq,
            kind=kind,
            vehicle_id=vehicle_id,
            payload=payload or {},
            event_id=self._event_ids,
        )
        heapq.heappush(self._heap, event)
        return event.event_id

    def _record(self, kind: str, vehicle_id: str | None, data: dict) -> None:
        self._log_seq += 1
        self.log.append(
            LogRecord(
                time=self.time,
                seq=self._log_seq,
                kind=kind,
                vehicle_id=vehicle_id,
                data=data,
            )
        )
