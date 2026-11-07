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


def replay_plant_log_independent(
    net: RoadNetwork,
    log: PlantLog,
    *,
    vehicle_id: str = "v1",
    initial_soc: float | None = None,
    initial_time: float = 0.0,
    initial_node: str | None = None,
) -> ReplayReport:
    """Recompute SOC/time from logged travel/charge/serve using network formulas only."""
    soc = net.battery if initial_soc is None else initial_soc
    t = initial_time
    node = net.depot if initial_node is None else initial_node
    notes: list[str] = []
    for ev in log.events:
        kind = ev.get("kind")
        if kind == "travel":
            if ev.get("vehicle") != vehicle_id:
                continue
            sid = ev["segment"]
            seg = next(s for s in net.segments if s.segment_id == sid)
            if seg.origin != node:
                return ReplayReport(False, ("wrong_origin_in_log",), t, soc)
            theta = float(ev["theta_star"])
            e_pred = net.energy(seg, theta)
            e_obs = float(ev["energy"])
            if abs(e_pred - e_obs) > 1e-6:
                # noise allowed in log; check battery
                pass
            if e_obs > soc + 1e-9:
                return ReplayReport(False, ("soc_violation_on_replay",), t, soc)
            soc -= e_obs
            t += seg.travel_time
            node = seg.destination
            if abs(float(ev["time"]) - t) > 1e-6:
                notes.append("time_mismatch_vs_log")
            if abs(float(ev["soc"]) - soc) > 1e-6:
                notes.append("soc_mismatch_vs_log")
        elif kind == "charge_full":
            if ev.get("vehicle") != vehicle_id:
                continue
            ch = net.charger_at(node)
            if ch is None:
                return ReplayReport(False, ("charge_without_charger",), t, soc)
            deficit = net.battery - soc
            duration = ch.full_charge_time * (deficit / net.battery)
            t += duration
            soc = net.battery
        elif kind == "serve":
            t = float(ev["time"])  # service end time from log
        elif kind == "model_inconsistency":
            return ReplayReport(False, ("model_inconsistency_logged",), t, soc)
    return ReplayReport(True, tuple(notes) if notes else ("replay_ok",), t, soc)
