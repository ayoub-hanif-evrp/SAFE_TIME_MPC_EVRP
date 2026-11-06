"""Event-log replay.

Expected travel energy for Euclidean benchmark instances is recomputed as
``consumption_rate * hypot(dx, dy)``. Charge duration is recomputed as
``inverse_recharge_rate * (target - soc_before)``. The optimizer's feasibility
flag is not consulted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from safe_time_evrp.models.instance import Instance, NodeKind
from safe_time_evrp.models.state import LogRecord

EPS = 1e-6


class ReplayRejection(Exception):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass
class ReplayReport:
    ok: bool
    announced: list[str]
    completed: list[str]
    rejected: list[str]
    accepted_unfulfilled: list[str]
    open_requests: list[str]
    code: str = "ok"
    detail: str = ""
    vehicles_en_route: list[str] = field(default_factory=list)


def validate_log(
    instance: Instance,
    log: list[LogRecord],
    *,
    claimed_summary: dict[str, list[str]] | None = None,
    energy_scale: float = 1.0,
) -> ReplayReport:
    try:
        report = _replay(instance, log, energy_scale)
    except ReplayRejection as exc:
        return ReplayReport(
            ok=False,
            announced=[],
            completed=[],
            rejected=[],
            accepted_unfulfilled=[],
            open_requests=[],
            code=exc.code,
            detail=str(exc),
        )
    if claimed_summary is not None:
        announced = set(report.announced)
        claimed_parts = []
        for key in ("completed", "rejected", "accepted_unfulfilled", "open_requests"):
            claimed_parts.extend(claimed_summary.get(key, []))
        buckets = {
            "completed": report.completed,
            "rejected": report.rejected,
            "accepted_unfulfilled": report.accepted_unfulfilled,
            "open_requests": report.open_requests,
        }
        same_partition = set(claimed_parts) == announced and len(claimed_parts) == len(set(claimed_parts))
        same_labels = all(sorted(claimed_summary.get(key, [])) == buckets[key] for key in buckets)
        if not same_partition or not same_labels:
            return ReplayReport(
                ok=False,
                announced=report.announced,
                completed=report.completed,
                rejected=report.rejected,
                accepted_unfulfilled=report.accepted_unfulfilled,
                open_requests=report.open_requests,
                code="denominator_mismatch",
                detail="claimed summary does not partition the announced requests",
            )
    return report


def _expected_energy(instance: Instance, origin: str, destination: str, scale: float) -> float:
    arc = instance.arc(origin, destination)
    if instance.source_format in {"schneider_2014", "euclidean", "synthetic"}:
        a = instance.node(origin)
        b = instance.node(destination)
        return scale * instance.vehicle_type.consumption_rate * math.hypot(a.x - b.x, a.y - b.y)
    return scale * arc.energy


def _replay(instance: Instance, log: list[LogRecord], scale: float) -> ReplayReport:
    vehicle = instance.vehicle_type
    state: dict[str, dict] = {}
    released_at: dict[str, float] = {}
    accepted: set[str] = set()
    rejected: set[str] = set()
    completed: list[str] = []
    open_trip: dict[str, dict | None] = {}

    ordered = sorted(log, key=lambda record: (record.time, record.seq))
    previous_time = -1.0
    for record in ordered:
        if record.time + EPS < previous_time:
            raise ReplayRejection("time_reversal", f"event {record.kind} moves backwards")
        previous_time = record.time
        kind = record.kind
        if kind == "vehicle_init":
            if record.vehicle_id is None:
                raise ReplayRejection("fleet_accounting", "init without a vehicle")
            state[record.vehicle_id] = {
                "node": record.data["node"],
                "soc": record.data["soc"],
                "load": record.data["load"],
                "busy": None,
            }
            open_trip[record.vehicle_id] = None
            _check_levels(vehicle, state[record.vehicle_id], "init")
            continue
        if kind == "request_release":
            customer_id = record.data["customer_id"]
            if customer_id in released_at:
                raise ReplayRejection("duplicate_release", customer_id)
            released_at[customer_id] = record.time
            continue
        if kind in {"decision", "replan_interval", "depot_idle"}:
            if kind == "decision":
                for customer_id in record.data.get("newly_accepted", []):
                    if customer_id not in released_at or released_at[customer_id] > record.time + EPS:
                        raise ReplayRejection("early_request_access", customer_id)
                    accepted.add(customer_id)
                for customer_id in record.data.get("rejected", []):
                    if customer_id not in released_at or released_at[customer_id] > record.time + EPS:
                        raise ReplayRejection("early_request_access", customer_id)
                    rejected.add(customer_id)
            continue
        if kind == "episode_end":
            for vid, end in record.data["vehicles"].items():
                current = state[vid]
                if current["node"] != end["node"] or abs(current["soc"] - end["soc"]) > EPS:
                    raise ReplayRejection("wrong_location", f"episode end mismatch for {vid}")
                if abs(current["load"] - end["load"]) > EPS:
                    raise ReplayRejection("fleet_accounting", f"episode end load mismatch for {vid}")
            continue
        if record.vehicle_id not in state:
            raise ReplayRejection("fleet_accounting", f"unknown vehicle {record.vehicle_id}")
        current = state[record.vehicle_id]
        if kind == "load_freight":
            if current["node"] != instance.depot_id:
                raise ReplayRejection("fleet_accounting", "freight loaded away from the depot")
            added = sum(instance.node(cid).demand for cid in record.data["customers"])
            current["load"] += added
            if abs(current["load"] - record.data["load"]) > EPS:
                raise ReplayRejection("fleet_accounting", "load event does not match demands")
            _check_levels(vehicle, current, "load")
            continue
        if kind == "reload":
            if current["node"] != instance.depot_id:
                raise ReplayRejection("fleet_accounting", "reload away from the depot")
            current["load"] = 0.0
            continue
        if kind == "depart":
            if current["busy"] is not None:
                raise ReplayRejection("interrupted_travel", record.vehicle_id or "")
            origin = record.data["origin"]
            destination = record.data["destination"]
            if current["node"] != origin:
                raise ReplayRejection("wrong_location", f"{record.vehicle_id} left from {origin}")
            energy_factor = float(record.data.get("energy_factor", scale))
            time_factor = float(record.data.get("time_factor", 1.0))
            if "energy_factor" in record.data:
                energy = _expected_energy(instance, origin, destination, energy_factor)
            else:
                energy = _expected_energy(instance, origin, destination, scale)
            travel = time_factor * instance.arc(origin, destination).travel_time
            if abs(record.data["energy"] - energy) > EPS:
                raise ReplayRejection("travel_energy", f"{origin}->{destination}")
            if abs(record.data["travel_time"] - travel) > EPS:
                raise ReplayRejection("travel_timing", f"{origin}->{destination}")
            if current["soc"] - energy < -EPS:
                raise ReplayRejection("negative_battery", record.vehicle_id or "")
            current["busy"] = {
                "kind": "travel",
                "destination": destination,
                "depart_time": record.time,
                "energy": energy,
                "travel_time": travel,
                "soc_before": current["soc"],
            }
            continue
        if kind == "arrive":
            trip = current["busy"]
            if trip is None or trip["kind"] != "travel":
                raise ReplayRejection("wrong_location", "arrival without travel")
            if record.data["destination"] != trip["destination"]:
                raise ReplayRejection("wrong_location", "arrival destination was changed")
            if abs(record.time - (trip["depart_time"] + trip["travel_time"])) > EPS:
                raise ReplayRejection("travel_timing", record.vehicle_id or "")
            expected_soc = trip["soc_before"] - trip["energy"]
            logged_soc = record.data["soc"]
            if logged_soc < -EPS:
                raise ReplayRejection("negative_battery", record.vehicle_id or "")
            if abs(logged_soc - expected_soc) > EPS:
                raise ReplayRejection("travel_energy", "arrival state of charge")
            current["soc"] = expected_soc
            current["node"] = trip["destination"]
            current["busy"] = None
            _check_levels(vehicle, current, "arrive")
            continue
        if kind == "depot_arrival":
            if current["node"] != instance.depot_id:
                raise ReplayRejection("depot_return", record.vehicle_id or "")
            continue
        if kind == "wait_start" or kind == "wait_end":
            if current["busy"] is not None:
                raise ReplayRejection("interrupted_travel", "wait during a locked action")
            continue
        if kind == "service_start":
            if current["busy"] is not None:
                raise ReplayRejection("interrupted_travel", "service during another action")
            customer_id = record.data["customer_id"]
            if customer_id not in released_at:
                raise ReplayRejection("early_request_access", customer_id)
            if record.time + EPS < released_at[customer_id]:
                raise ReplayRejection("early_request_access", customer_id)
            node = instance.node(customer_id)
            if current["node"] != customer_id or node.kind is not NodeKind.CUSTOMER:
                raise ReplayRejection("wrong_location", customer_id)
            if record.time > node.window.due + EPS:
                raise ReplayRejection("missed_window", customer_id)
            if customer_id in completed:
                raise ReplayRejection("duplicate_service", customer_id)
            demand = node.demand
            if current["load"] - demand < -EPS:
                raise ReplayRejection("fleet_accounting", customer_id)
            current["load"] -= demand
            if abs(current["load"] - record.data["load"]) > EPS:
                raise ReplayRejection("fleet_accounting", "service load")
            current["busy"] = {
                "kind": "service",
                "customer_id": customer_id,
                "end": record.time + node.service_time,
            }
            _check_levels(vehicle, current, "service")
            continue
        if kind == "service_end":
            customer_id = record.data["customer_id"]
            if customer_id in completed:
                raise ReplayRejection("duplicate_service", customer_id)
            trip = current["busy"]
            if trip is None or trip["kind"] != "service" or trip["customer_id"] != customer_id:
                raise ReplayRejection("interrupted_travel", "service end without service")
            if abs(record.time - trip["end"]) > EPS:
                raise ReplayRejection("travel_timing", f"service duration {customer_id}")
            if customer_id in completed:
                raise ReplayRejection("duplicate_service", customer_id)
            completed.append(customer_id)
            current["busy"] = None
            continue
        if kind == "charge_start":
            if current["busy"] is not None:
                raise ReplayRejection("interrupted_travel", "charge during another action")
            station_id = record.data["station"]
            station = instance.node(station_id)
            if station.kind is not NodeKind.CHARGER or current["node"] != station_id:
                raise ReplayRejection("impossible_charge", station_id)
            target = record.data["target"]
            soc_before = record.data["soc"]
            if abs(soc_before - current["soc"]) > EPS:
                raise ReplayRejection("impossible_charge", "charge does not start from the current soc")
            if target > vehicle.battery_capacity + EPS or target < soc_before - EPS:
                raise ReplayRejection("impossible_charge", "target outside the battery")
            duration = vehicle.inverse_recharge_rate * max(0.0, target - soc_before)
            if abs(record.data["duration"] - duration) > EPS:
                raise ReplayRejection("impossible_charge", "duration does not match the linear rate")
            current["busy"] = {
                "kind": "charge",
                "end": record.time + duration,
                "target": target,
            }
            continue
        if kind == "charge_end":
            trip = current["busy"]
            if trip is None or trip["kind"] != "charge":
                raise ReplayRejection("impossible_charge", "charge end without charge")
            if abs(record.time - trip["end"]) > EPS:
                raise ReplayRejection("impossible_charge", "charge ended early")
            if abs(record.data["soc"] - trip["target"]) > EPS:
                raise ReplayRejection("impossible_charge", "soc does not reach the target")
            current["soc"] = trip["target"]
            current["busy"] = None
            _check_levels(vehicle, current, "charge")
            continue
        raise ReplayRejection("fleet_accounting", f"unrecognized event {kind}")

    for current in state.values():
        if current["busy"] is not None:
            # A truncated episode may end inside a noninterruptible action.
            # That is reported, and it is not rewritten into a completion.
            pass
    announced = sorted(released_at)
    completed_set = set(completed)
    rejected_set = set(rejected)
    if completed_set & rejected_set:
        raise ReplayRejection("duplicate_service", "completed request was also rejected")
    accepted_unfulfilled = sorted(cid for cid in accepted if cid not in completed_set and cid not in rejected_set)
    open_requests = sorted(
        cid
        for cid in announced
        if cid not in completed_set and cid not in rejected_set and cid not in set(accepted_unfulfilled)
    )
    # Accepted customers who are still in service are unfulfilled until service_end.
    en_route = [
        vid for vid, current in state.items() if current["node"] != instance.depot_id or current["busy"] is not None
    ]
    return ReplayReport(
        ok=True,
        announced=announced,
        completed=sorted(completed),
        rejected=sorted(rejected_set),
        accepted_unfulfilled=accepted_unfulfilled,
        open_requests=open_requests,
        vehicles_en_route=en_route,
    )


def _check_levels(vehicle, current: dict, where: str) -> None:
    if current["soc"] < -EPS:
        raise ReplayRejection("negative_battery", where)
    if current["soc"] > vehicle.battery_capacity + EPS:
        raise ReplayRejection("impossible_charge", where)
    if current["load"] < -EPS or current["load"] > vehicle.load_capacity + EPS:
        raise ReplayRejection("excess_payload", where)
