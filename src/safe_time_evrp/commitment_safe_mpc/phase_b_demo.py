"""Phase B closed-loop demonstration on the authoritative FleetSimulator plant.

Completion criteria (all required):
  - two vehicles operate
  - several customers arrive dynamically
  - at least one charging action occurs
  - controller replans multiple times
  - accepted commitments are fulfilled
  - independent replay accepts the trajectory

The demo controller is a **plant-verification** policy with an explicit feasible
charge plan. It is not the research baseline (B0 ALNS lands in Phase C).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.plant import verify_episode_log
from safe_time_evrp.environment.energy import EPS
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import (
    Instance,
    Node,
    NodeKind,
    TimeWindow,
    VehicleType,
    build_euclidean_instance,
)
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.validation.replay import ReplayReport

_TRIGGERS = {
    "request_release",
    "arrive",
    "service_end",
    "charge_end",
    "wait_end",
    "replan_interval",
}


def make_phase_b_instance() -> Instance:
    """Two-EV geometry: v1 needs a charge to finish the east corridor; v2 serves north."""
    # Without charging, D→C1→C2→D ≈ 32.5 > 22, so v1 must charge. North tour fits in 22.
    vehicle = VehicleType(
        battery_capacity=22.0,
        load_capacity=20.0,
        consumption_rate=1.0,
        inverse_recharge_rate=0.25,
        velocity=1.0,
        recharge_policy="full",
    )
    nodes = [
        Node("D", NodeKind.DEPOT, 0.0, 0.0, 0.0, TimeWindow(0.0, 500.0), 0.0),
        Node("S", NodeKind.CHARGER, 8.0, 0.0, 0.0, TimeWindow(0.0, 500.0), 0.0),
        Node("C1", NodeKind.CUSTOMER, 8.0, 2.0, 1.0, TimeWindow(0.0, 200.0), 2.0),
        Node("C2", NodeKind.CUSTOMER, 16.0, 0.0, 1.0, TimeWindow(0.0, 280.0), 2.0),
        Node("C3", NodeKind.CUSTOMER, 0.0, 8.0, 1.0, TimeWindow(50.0, 320.0), 2.0),
        Node("C4", NodeKind.CUSTOMER, 0.0, 10.0, 1.0, TimeWindow(50.0, 360.0), 2.0),
    ]
    return build_euclidean_instance(
        "phase_b_commitment_demo",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="commitment-safe-phase-b",
        assumptions=(
            "Synthetic Euclidean plant-verification instance.",
            "East corridor requires charging under battery_capacity=18.",
            "North corridor assigned to the second vehicle after dynamic release.",
        ),
        metadata={"phase": "B", "purpose": "authoritative_plant_demo"},
    )


def phase_b_releases() -> list[tuple[str, float]]:
    # C3/C4 released together so v2 can load both at the depot in one tour.
    return [("C1", 0.0), ("C2", 0.0), ("C3", 50.0), ("C4", 50.0)]


class ChargeAwareDemoController:
    """Explicit feasible multi-EV plan with a mandatory charge on v1.

    Accepts all announced customers that appear in the declared assignment.
    Rejects nothing that is assigned. Not an optimizing baseline.
    """

    def __init__(self, instance: Instance) -> None:
        self.instance = instance
        self._accepted: set[str] = set()

    def decide(self, observation: Observation, trigger: str) -> Decision:
        t0 = perf_counter()
        open_ids = set(observation.released_open) | set(observation.accepted)
        newly: list[str] = []
        for cid in ("C1", "C2", "C3", "C4"):
            if cid in open_ids and cid not in self._accepted and cid not in observation.completed:
                if cid in observation.released_open or cid in observation.accepted:
                    newly.append(cid)
                    self._accepted.add(cid)
        accepted = sorted(self._accepted - set(observation.completed) - set(observation.rejected))

        routes: dict[str, list[Visit]] = {v.id: [] for v in observation.vehicles}
        # East corridor on v1: C1 -> charge at S -> C2 -> depot
        v1_plan: list[Visit] = []
        if "C1" in accepted or "C1" in observation.in_service:
            if "C1" not in observation.completed:
                v1_plan.append(Visit("C1", "service"))
        if "C2" in accepted or "C2" in observation.in_service:
            if "C2" not in observation.completed:
                # Charge before the long second leg whenever C2 still pending
                if "C1" in observation.completed or any(v.node_id == "C1" for v in v1_plan):
                    v1_plan.append(Visit("S", "charge"))
                elif "C1" not in accepted and "C1" not in observation.completed:
                    v1_plan.append(Visit("S", "charge"))
                v1_plan.append(Visit("C2", "service"))
        v1 = next(v for v in observation.vehicles if v.id == "v1")
        if v1_plan:
            v1_plan.append(Visit("D", "return"))
        elif (
            v1.node != self.instance.depot_id
            and v1.locked_destination is None
            and "C1" in observation.completed
            and "C2" in observation.completed
        ):
            v1_plan = _return_via_charge_if_needed(self.instance, v1.node, v1.soc)
        routes["v1"] = v1_plan

        # North corridor on v2: load all pending north customers from the depot.
        # If SOC is too low for a direct tour, recharge at S first.
        v2 = next(v for v in observation.vehicles if v.id == "v2")
        v2_plan: list[Visit] = []
        pending_north = [cid for cid in ("C3", "C4") if cid in accepted and cid not in observation.completed]
        if v2.node == self.instance.depot_id and v2.locked_destination is None:
            if pending_north:
                need = _north_tour_energy(self.instance, pending_north)
                if v2.soc + EPS < need:
                    v2_plan.append(Visit("S", "charge"))
                for cid in pending_north:
                    v2_plan.append(Visit(cid, "service"))
                v2_plan.append(Visit("D", "return"))
        else:
            for cid in pending_north:
                if cid in v2.onboard or cid in observation.in_service:
                    v2_plan.append(Visit(cid, "service"))
            if v2_plan or any(cid in v2.onboard for cid in pending_north):
                v2_plan.append(Visit("D", "return"))
            elif v2.node != self.instance.depot_id and not pending_north:
                v2_plan = [Visit("D", "return")]
        routes["v2"] = v2_plan

        completed = set(observation.completed)
        for vehicle in observation.vehicles:
            if vehicle.locked_destination is not None:
                continue
            routes[vehicle.id] = _trim_completed_prefix(routes.get(vehicle.id, []), vehicle.node, completed)

        planned = [v.node_id for visits in routes.values() for v in visits if v.purpose == "service"]
        locked = {v.id: v.locked_destination for v in observation.vehicles}
        return Decision(
            time=observation.time,
            routes=routes,
            accepted=accepted,
            newly_accepted=newly,
            rejected=[],
            deferred=[],
            fallback_used=False,
            no_feasible_continuation=False,
            horizon_extended=False,
            planned_service=planned,
            total_distance=0.0,
            total_charge_time=1.0 if any(v.purpose == "charge" for vs in routes.values() for v in vs) else 0.0,
            optimize_seconds=perf_counter() - t0,
            trigger=trigger,
            locked_destinations=locked,
            notes=["phase_b_demo_controller", f"trigger={trigger}"],
        )


def _return_via_charge_if_needed(instance: Instance, node: str, soc: float) -> list[Visit]:
    depot = instance.depot_id
    if node == depot:
        return []
    direct = instance.arc(node, depot).energy
    if soc + EPS >= direct:
        return [Visit(depot, "return")]
    station = instance.charger_ids()[0]
    if node == station:
        return [Visit(station, "charge"), Visit(depot, "return")]
    via = instance.arc(node, station).energy
    if soc + EPS < via:
        return [Visit(depot, "return")]
    return [Visit(station, "charge"), Visit(depot, "return")]


def _north_tour_energy(instance: Instance, customers: list[str]) -> float:
    """Optimistic lower bound: depot → customers in order → depot."""
    if not customers:
        return 0.0
    energy = instance.arc(instance.depot_id, customers[0]).energy
    for a, b in zip(customers, customers[1:], strict=False):
        energy += instance.arc(a, b).energy
    energy += instance.arc(customers[-1], instance.depot_id).energy
    return energy


def _trim_completed_prefix(visits: list[Visit], node: str, completed: set[str]) -> list[Visit]:
    """Drop completed services; never treat a later depot return as 'already here'."""
    i = 0
    while i < len(visits):
        visit = visits[i]
        if visit.purpose == "service" and visit.node_id in completed:
            i += 1
            continue
        if visit.purpose == "charge" and i + 1 < len(visits):
            # Skip a charge that only preceded already-completed work
            nxt = visits[i + 1]
            if nxt.purpose == "service" and nxt.node_id in completed:
                i += 1
                continue
        break
    remaining = visits[i:]
    for j, visit in enumerate(remaining):
        if visit.node_id == node and visit.purpose in {"service", "charge"}:
            return remaining[j:]
    return remaining


@dataclass
class PhaseBDemoResult:
    instance_name: str
    replay_ok: bool
    replay_code: str
    final_requests: dict[str, str]
    n_decisions: int
    n_vehicles_that_served: int
    n_charge_starts: int
    n_dynamic_releases_after_zero: int
    accepted_unfulfilled: list[str]
    completed: list[str]
    triggers: list[str]
    criteria: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def run_phase_b_demo(
    *,
    fleet_size: int = 2,
    max_replan_interval: float = 25.0,
    t_max: float = 500.0,
    max_events: int = 20_000,
) -> tuple[PhaseBDemoResult, list, ReplayReport]:
    instance = make_phase_b_instance()
    releases = phase_b_releases()
    sim = FleetSimulator(instance, fleet_size)
    for cid, t in releases:
        sim.schedule_release(cid, t)
    controller = ChargeAwareDemoController(instance)
    decisions: list[Decision] = []
    replan_id: int | None = None

    def decide(trigger: str) -> None:
        nonlocal replan_id
        decision = controller.decide(sim.observation(), trigger)
        decisions.append(decision)
        sim.apply_decision(decision)
        if replan_id is not None:
            sim.cancel(replan_id)
            replan_id = None
        if not _finished(sim):
            replan_id = sim.schedule_replan(sim.time + max_replan_interval)

    if sim.next_event_time() is None or sim.next_event_time() > EPS:
        decide("initial")
    events = 0
    while events < max_events:
        nxt = sim.next_event_time()
        if nxt is None or nxt > t_max + EPS:
            break
        # Coalesce all same-time events so simultaneous releases share one decision.
        batch_time = nxt
        triggers: list[str] = []
        while sim.next_event_time() is not None and abs(sim.next_event_time() - batch_time) <= EPS:
            event = sim.pop_event()
            events += 1
            if event is None:
                break
            if event.kind in _TRIGGERS:
                triggers.append(event.kind)
            if events >= max_events:
                break
        if triggers:
            decide("+".join(sorted(set(triggers))))
        if _finished(sim):
            break
    else:
        raise RuntimeError("phase_b_demo hit event limit")
    sim.mark_finished()
    report = verify_episode_log(instance, sim.log)
    charge_starts = sum(1 for r in sim.log if r.kind == "charge_start")
    served_vids = {r.vehicle_id for r in sim.log if r.kind == "service_start" and r.vehicle_id}
    dynamic = sum(1 for _, t in releases if t > EPS)
    criteria = {
        "two_vehicles_operate": len(served_vids) >= 2,
        "dynamic_arrivals": dynamic >= 2,
        "charging_occurred": charge_starts >= 1,
        "multiple_replans": len(decisions) >= 2,
        "accepted_commitments_fulfilled": report.ok and not report.accepted_unfulfilled,
        "independent_replay_accepts": report.ok,
    }
    result = PhaseBDemoResult(
        instance_name=instance.name,
        replay_ok=report.ok,
        replay_code=report.code,
        final_requests={cid: s.value for cid, s in sim.requests.items()},
        n_decisions=len(decisions),
        n_vehicles_that_served=len(served_vids),
        n_charge_starts=charge_starts,
        n_dynamic_releases_after_zero=dynamic,
        accepted_unfulfilled=list(report.accepted_unfulfilled),
        completed=list(report.completed),
        triggers=[d.trigger for d in decisions],
        criteria=criteria,
        notes=[] if all(criteria.values()) else [k for k, v in criteria.items() if not v],
    )
    return result, sim.log, report


def _finished(sim: FleetSimulator) -> bool:
    open_status = {"announced", "accepted", "deferred", "in_service"}
    if any(s.value in open_status for s in sim.requests.values()):
        return False
    if any(sim.requests[cid].value == "hidden" for cid in sim.release_time):
        return False
    depot = sim.instance.depot_id
    return all(v.status.value == "idle" and v.node == depot for v in sim.vehicles.values())


def write_phase_b_artifact(out_dir: Path) -> dict:
    result, _log, report = run_phase_b_demo()
    payload = {
        "result": asdict(result),
        "replay": {
            "ok": report.ok,
            "code": report.code,
            "completed": report.completed,
            "accepted_unfulfilled": report.accepted_unfulfilled,
            "announced": report.announced,
        },
        "all_criteria_met": all(result.criteria.values()),
        "plant": "safe_time_evrp.environment.simulator.FleetSimulator",
        "replay_module": "safe_time_evrp.validation.replay.validate_log",
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "phase_b_demo.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    art = write_phase_b_artifact(Path("docs/commitment_safe_mpc"))
    print(json.dumps({k: art[k] for k in ("all_criteria_met", "result")}, indent=2))
