"""Independent trajectory replay from PlantLog (does not call apply_action)."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.network import RoadNetwork
from safe_time_evrp.dr_dual.state import PlantLog


@dataclass(frozen=True)
class ReplayReport:
    ok: bool
    notes: tuple[str, ...]
    final_time: float | None
    final_soc: float | None
    final_node: str | None = None


def replay_plant_log_independent(
    net: RoadNetwork,
    log: PlantLog,
    *,
    vehicle_id: str = "v1",
    initial_soc: float | None = None,
    initial_time: float = 0.0,
    initial_node: str | None = None,
    accepted: frozenset[str] | None = None,
    completed_required: frozenset[str] | None = None,
    require_depot_return: bool = False,
    noise_tol: float = 1e-6,
) -> ReplayReport:
    """Recompute SOC/time from logged travel/charge/serve using network formulas only.

    Physical mismatches (SOC, time, origin, energy without declared noise) yield ok=False.
    """
    soc = net.battery if initial_soc is None else initial_soc
    t = initial_time
    node = net.depot if initial_node is None else initial_node
    notes: list[str] = []
    completed: set[str] = set()
    for ev in log.events:
        kind = ev.get("kind")
        if kind == "travel":
            if ev.get("vehicle") != vehicle_id:
                continue
            sid = ev["segment"]
            seg = next(s for s in net.segments if s.segment_id == sid)
            if seg.origin != node:
                return ReplayReport(False, ("wrong_origin_in_log",), t, soc, node)
            if "origin" in ev and ev["origin"] != seg.origin:
                return ReplayReport(False, ("origin_field_mismatch",), t, soc, node)
            theta = float(ev["theta_star"])
            e_pred = net.energy(seg, theta)
            e_obs = float(ev["energy"])
            if abs(e_pred - e_obs) > noise_tol + 1e-9:
                # Without an explicit logged noise budget, reject unexplained energy mismatch
                if "noise" not in ev and abs(e_pred - e_obs) > 1e-6:
                    return ReplayReport(False, ("energy_mismatch_vs_theta",), t, soc, node)
            if e_obs > soc + 1e-9:
                return ReplayReport(False, ("soc_violation_on_replay",), t, soc, node)
            soc -= e_obs
            t += seg.travel_time
            node = seg.destination
            if abs(float(ev["time"]) - t) > 1e-6:
                return ReplayReport(False, ("time_mismatch_vs_log",), t, soc, node)
            if abs(float(ev["soc"]) - soc) > 1e-6:
                return ReplayReport(False, ("soc_mismatch_vs_log",), t, soc, node)
        elif kind == "charge_full":
            if ev.get("vehicle") != vehicle_id:
                continue
            if "node" in ev and ev["node"] != node:
                return ReplayReport(False, ("charge_node_mismatch",), t, soc, node)
            ch = net.charger_at(node)
            if ch is None:
                return ReplayReport(False, ("charge_without_charger",), t, soc, node)
            deficit = net.battery - soc
            duration = ch.full_charge_time * (deficit / net.battery)
            t += duration
            soc = net.battery
            if "time" in ev and abs(float(ev["time"]) - t) > 1e-6:
                return ReplayReport(False, ("charge_time_mismatch",), t, soc, node)
        elif kind == "serve":
            if ev.get("vehicle") not in (None, vehicle_id):
                if ev.get("vehicle") != vehicle_id:
                    continue
            cid = ev["customer"]
            cust = net.customer(cid)
            if "node" in ev and ev["node"] != cust.node:
                return ReplayReport(False, ("serve_node_mismatch",), t, soc, node)
            if node != cust.node:
                return ReplayReport(False, ("not_at_customer_on_replay",), t, soc, node)
            start = max(t, cust.ready)
            end = start + cust.service_time
            if abs(float(ev["time"]) - end) > 1e-6:
                return ReplayReport(False, ("serve_time_mismatch",), t, soc, node)
            t = end
            completed.add(cid)
        elif kind == "model_inconsistency":
            # Physics already committed in prior travel event; flag only.
            notes.append("model_inconsistency_after_travel")
    if completed_required is not None and not completed_required.issubset(completed):
        return ReplayReport(False, ("accepted_not_completed",), t, soc, node)
    if accepted is not None and not accepted.issubset(completed | (accepted & completed)):
        # If accepted provided without completed_required, require accepted ⊆ completed
        if not accepted.issubset(completed):
            return ReplayReport(False, ("accepted_not_completed",), t, soc, node)
    if require_depot_return and node != net.depot:
        return ReplayReport(False, ("depot_return_missing",), t, soc, node)
    return ReplayReport(True, tuple(notes) if notes else ("replay_ok",), t, soc, node)
