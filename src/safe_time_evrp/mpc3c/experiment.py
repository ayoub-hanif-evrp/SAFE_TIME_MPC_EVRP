"""Matched dynamic experiments for Gate 3C controllers."""

from __future__ import annotations

from dataclasses import dataclass, field

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.testbed.validator import validate_fleet_plan


@dataclass
class StepLog:
    time: float
    kind: str
    first_actions: dict[str, str | None]
    served_total: int
    notes: list[str] = field(default_factory=list)


@dataclass
class RunResult:
    controller: str
    served: list[str]
    rejected: list[str]
    commitment_violations: int
    charge_events: int
    steps: list[StepLog]
    final_feasible_plan: bool
    first_action_signature: str


def _obs(
    time: float,
    vehicles: list[VehicleView],
    released: list[str],
    accepted: list[str],
    completed: list[str],
    rejected: list[str],
) -> Observation:
    return Observation(
        time,
        tuple(vehicles),
        tuple(released),
        tuple(accepted),
        tuple(completed),
        tuple(rejected),
        (),
        (),
    )


def run_dynamic(
    instance: Instance,
    kind: ControllerKind,
    *,
    fleet_size: int = 2,
    horizon: float = 4.0,
    max_steps: int = 40,
) -> RunResult:
    """Release customers when time reaches window.ready; irrevocable accept on plan inclusion."""
    soc0 = instance.vehicle_type.battery_capacity
    vehicles = [
        VehicleView(
            f"v{i}",
            "idle",
            instance.depot_id,
            soc0,
            0.0,
            (),
            Anchor(instance.depot_id, 0.0, soc0, 0.0, frozenset()),
            None,
        )
        for i in range(fleet_size)
    ]
    pending = set(instance.customer_ids())
    accepted: list[str] = []
    completed: list[str] = []
    rejected: list[str] = []
    time = 0.0
    steps: list[StepLog] = []
    charge_events = 0
    commitment_violations = 0
    model = NominalLinearEnergy()
    first_sig = ""
    routes: dict[str, list[Visit]] = {v.id: [] for v in vehicles}

    for step in range(max_steps):
        # Release by ready time.
        released = sorted(
            cid
            for cid in instance.customer_ids()
            if cid not in completed and cid not in rejected and instance.node(cid).window.ready <= time + 1e-9
        )
        # Drop stale accepted that somehow completed.
        accepted = [c for c in accepted if c not in completed and c not in rejected]
        obs = _obs(time, vehicles, released, accepted, completed, rejected)
        decision = decide(instance, obs, kind, horizon=horizon)
        routes = decision.routes
        if step == 0:
            first_sig = str(
                sorted(
                    (vid, (a.node_id if a else None, a.purpose if a else None))
                    for vid, a in decision.first_actions.items()
                )
            )
        # Accept customers appearing in routes.
        for visits in routes.values():
            for visit in visits:
                if visit.purpose == "service" and visit.node_id not in accepted:
                    accepted.append(visit.node_id)
        # Execute first action for each vehicle (one visit), advance time to max end.
        new_vehicles: list[VehicleView] = []
        advanced = False
        for vehicle in vehicles:
            action = decision.first_actions.get(vehicle.id)
            # Ignore depot no-ops (empty plan finalized as immediate return).
            if action is None or (action.purpose == "return" and vehicle.anchor.node == instance.depot_id):
                new_vehicles.append(vehicle)
                continue
            suffix = [action]
            result = evaluate_route(instance, vehicle.anchor, suffix, model)
            if not result.feasible:
                if action.purpose == "service" and action.node_id in accepted:
                    commitment_violations += 1
                new_vehicles.append(vehicle)
                continue
            if result.end_time <= time + 1e-12 and action.node_id == vehicle.anchor.node:
                new_vehicles.append(vehicle)
                continue
            advanced = True
            if action.purpose == "charge":
                charge_events += 1
            if action.purpose == "service":
                completed.append(action.node_id)
                pending.discard(action.node_id)
            new_anchor = Anchor(result.end_node, result.end_time, result.end_soc, result.end_load, frozenset())
            new_vehicles.append(
                VehicleView(
                    vehicle.id,
                    "idle",
                    new_anchor.node,
                    new_anchor.soc,
                    new_anchor.load,
                    (),
                    new_anchor,
                    None,
                )
            )
            time = max(time, result.end_time)
        vehicles = new_vehicles
        steps.append(
            StepLog(
                time,
                kind.value,
                {vid: (a.node_id if a else None) for vid, a in decision.first_actions.items()},
                len(completed),
                decision.notes,
            )
        )
        if not pending - set(rejected) and set(accepted) <= set(completed):
            break
        if not advanced:
            # Force time forward to next release or quit.
            futures = [
                instance.node(cid).window.ready
                for cid in instance.customer_ids()
                if instance.node(cid).window.ready > time + 1e-9 and cid not in completed
            ]
            if not futures:
                # Reject remaining unaccepted/unserved.
                for cid in list(pending):
                    if cid not in completed:
                        rejected.append(cid)
                        pending.discard(cid)
                break
            time = min(futures)
        if step == max_steps - 1:
            for cid in list(pending):
                if cid not in completed:
                    if cid in accepted:
                        commitment_violations += 1
                    rejected.append(cid)

    # Final full replan feasibility check for residual accepted.
    obs = _obs(time, vehicles, [], [c for c in accepted if c not in completed], completed, rejected)
    decision = decide(instance, obs, kind, horizon=horizon)
    report = validate_fleet_plan(instance, decision.routes, start_time=time, require_all_customers=False)
    return RunResult(
        controller=kind.value,
        served=sorted(set(completed)),
        rejected=sorted(set(rejected)),
        commitment_violations=commitment_violations,
        charge_events=charge_events,
        steps=steps,
        final_feasible_plan=report.feasible,
        first_action_signature=first_sig,
    )


def compare_controllers(instance: Instance, *, fleet_size: int = 2, horizon: float = 4.0) -> dict:
    results = {}
    for kind in ControllerKind:
        results[kind.value] = run_dynamic(instance, kind, fleet_size=fleet_size, horizon=horizon)
    # Summarize action divergence vs RH.
    rh_sig = results[ControllerKind.RH_OPEN_LOOP.value].first_action_signature
    return {
        "instance": instance.name,
        "fleet_size": fleet_size,
        "horizon": horizon,
        "results": {
            name: {
                "served": r.served,
                "n_served": len(r.served),
                "rejected": r.rejected,
                "commitment_violations": r.commitment_violations,
                "charge_events": r.charge_events,
                "first_action_signature": r.first_action_signature,
                "differs_from_rh": r.first_action_signature != rh_sig,
                "n_steps": len(r.steps),
            }
            for name, r in results.items()
        },
    }
