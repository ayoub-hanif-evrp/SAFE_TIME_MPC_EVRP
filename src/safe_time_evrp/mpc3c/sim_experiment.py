"""Simulator-backed Gate 3D closed-loop experiment harness.

Replaces Gate 3C ``run_dynamic`` microtrip evaluation. Controllers emit full
suffixes; ``FleetSimulator`` executes them with noninterruptibility, preserved
unexecuted suffix, and event-queue time advance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, Visit
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, visible_forecast
from safe_time_evrp.robust.backup import dispatch_suffix
from safe_time_evrp.validation.replay import validate_log

_TRIGGERS = {
    "request_release",
    "arrive",
    "service_end",
    "charge_end",
    "wait_end",
    "replan_interval",
}


@dataclass
class StepLog:
    time: float
    kind: str
    first_actions: dict[str, str | None]
    served_total: int
    notes: list[str] = field(default_factory=list)
    trigger: str = ""


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
    action_sequence: list[tuple[float, str, str | None, str | None]]
    distance: float
    optimize_seconds: float
    log: list
    replay_ok: bool
    decision_event_signatures: list[str]


def _strip_unreleased(visits: list[Visit], released: set[str], completed: set[str]) -> list[Visit]:
    """Drop provisional forecast services that are not yet plant-released."""
    out: list[Visit] = []
    for visit in visits:
        if visit.purpose == "service" and visit.node_id not in released and visit.node_id not in completed:
            continue
        out.append(visit)
    return out


def _to_decision(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    *,
    newly_accepted: list[str],
    rejected: list[str],
    deferred: list[str],
    accepted: list[str],
    planned_service: list[str],
    total_distance: float,
    total_charge_time: float,
    optimize_seconds: float,
    trigger: str,
    notes: list[str],
) -> Decision:
    q = instance.vehicle_type.battery_capacity
    released = set(observation.released_open) | set(observation.accepted) | set(observation.in_service)
    completed = set(observation.completed)
    applied: dict[str, list[Visit]] = {}
    for vehicle in observation.vehicles:
        raw = routes.get(vehicle.id, [])
        cleaned = _strip_unreleased(raw, released, completed)
        applied[vehicle.id] = dispatch_suffix(
            cleaned,
            observation,
            vehicle.node,
            vehicle.soc,
            q,
        )
    locked = {vehicle.id: vehicle.locked_destination for vehicle in observation.vehicles}
    return Decision(
        time=observation.time,
        routes=applied,
        accepted=list(accepted),
        newly_accepted=list(newly_accepted),
        rejected=list(rejected),
        deferred=list(deferred),
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=list(planned_service),
        total_distance=total_distance,
        total_charge_time=total_charge_time,
        optimize_seconds=optimize_seconds,
        trigger=trigger,
        locked_destinations=locked,
        notes=list(notes),
    )


def _action_sig(decision: Decision) -> str:
    parts = []
    for vid in sorted(decision.routes):
        visits = decision.routes[vid]
        if not visits:
            parts.append(f"{vid}:None")
            continue
        first = visits[0]
        parts.append(f"{vid}:{first.node_id}:{first.purpose}")
    return "|".join(parts)


def _hamming(a: list[tuple], b: list[tuple]) -> int:
    n = max(len(a), len(b))
    d = 0
    for i in range(n):
        if i >= len(a) or i >= len(b) or a[i] != b[i]:
            d += 1
    return d


def run_sim_dynamic(
    instance: Instance,
    kind: ControllerKind,
    *,
    fleet_size: int = 2,
    horizon: float = 4.0,
    releases: list[tuple[str, float]] | None = None,
    forecast: ArrivalForecast | None = None,
    max_replan_interval: float | None = None,
    t_max: float | None = None,
    max_events: int = 20_000,
    energy: NominalLinearEnergy | None = None,
    disturbance=None,
) -> RunResult:
    """Closed-loop episode through ``FleetSimulator`` with Gate 3D controllers."""
    model = energy or NominalLinearEnergy()
    if releases is None:
        releases = [(cid, float(instance.node(cid).window.ready)) for cid in instance.customer_ids()]
    if t_max is None:
        t_max = max(instance.node(cid).window.due for cid in instance.customer_ids()) + 50.0
    if max_replan_interval is None:
        max_replan_interval = max(horizon, 1.0)

    simulator = FleetSimulator(instance, fleet_size, energy=model, disturbance=disturbance)
    for customer_id, release_time in releases:
        simulator.schedule_release(customer_id, release_time)

    steps: list[StepLog] = []
    decisions: list[Decision] = []
    action_sequence: list[tuple[float, str, str | None, str | None]] = []
    signatures: list[str] = []
    optimize_seconds = 0.0
    replan_id: int | None = None
    same_time = 0
    last_decision_time = -1.0
    first_sig = ""

    def decide_once(trigger: str) -> None:
        nonlocal optimize_seconds, replan_id, same_time, last_decision_time, first_sig
        if abs(simulator.time - last_decision_time) <= EPS:
            same_time += 1
        else:
            same_time = 0
            last_decision_time = simulator.time
        if same_time > 32:
            raise RuntimeError("decision loop did not advance time")

        observation = simulator.observation()
        # Idle/replan anchors must sit at plant time (Gate 3D desync contract).
        for vehicle in observation.vehicles:
            if vehicle.status == "idle" and abs(vehicle.anchor.time - observation.time) > EPS:
                raise RuntimeError(
                    f"anchor desync {vehicle.id}: anchor.t={vehicle.anchor.time} plant.t={observation.time}"
                )

        forecast_customers = visible_forecast(observation, forecast, horizon) if forecast else []
        wall = perf_counter()
        ctrl = decide(
            instance,
            observation,
            kind,
            horizon=horizon,
            forecast_customers=forecast_customers,
        )
        elapsed = perf_counter() - wall
        optimize_seconds += elapsed

        truly_released = set(observation.released_open)
        planned_released = _served(ctrl.routes) & truly_released
        newly = sorted(c for c in planned_released if c not in observation.accepted and c not in observation.in_service)
        accepted_out = list(observation.accepted)
        for cid in newly:
            if cid not in accepted_out:
                accepted_out.append(cid)
        # Do not reject customers whose windows have not opened yet (Gate 3D).
        # Horizon-deferred optionals stay deferred; irrevocable reject only after ready.
        deferred = [
            c
            for c in observation.released_open
            if c not in accepted_out
            and c not in observation.completed
            and c not in observation.in_service
            and (
                instance.node(c).window.ready > observation.time + 1e-9
                or instance.node(c).window.ready > observation.time + horizon
            )
        ]
        rejected = [
            c
            for c in observation.released_open
            if c not in accepted_out
            and c not in observation.completed
            and c not in observation.in_service
            and c not in deferred
            and c not in planned_released
        ]
        decision = _to_decision(
            instance,
            observation,
            ctrl.routes,
            newly_accepted=newly,
            rejected=rejected,
            deferred=deferred,
            accepted=accepted_out,
            planned_service=sorted(_served(ctrl.routes) & truly_released),
            total_distance=0.0,
            total_charge_time=0.0,
            optimize_seconds=elapsed,
            trigger=trigger,
            notes=ctrl.notes,
        )
        if not first_sig:
            first_sig = _action_sig(decision)
        signatures.append(_action_sig(decision))
        for vid in sorted(decision.routes):
            visits = decision.routes[vid]
            if visits:
                first = visits[0]
                action_sequence.append((observation.time, vid, first.node_id, first.purpose))
            else:
                action_sequence.append((observation.time, vid, None, None))
        steps.append(
            StepLog(
                observation.time,
                kind.value,
                {vid: (visits[0].node_id if visits else None) for vid, visits in decision.routes.items()},
                sum(1 for s in simulator.requests.values() if s.value == "completed"),
                list(ctrl.notes),
                trigger=trigger,
            )
        )
        decisions.append(decision)
        simulator.apply_decision(decision)
        if replan_id is not None:
            simulator.cancel(replan_id)
        replan_id = simulator.schedule_replan(simulator.time + max_replan_interval)

    if simulator.next_event_time() is None or simulator.next_event_time() > EPS:
        decide_once("initial")
    events = 0
    while events < max_events:
        nxt = simulator.next_event_time()
        if nxt is None or nxt > t_max + EPS:
            break
        event = simulator.pop_event()
        events += 1
        if event is None:
            break
        if event.kind in _TRIGGERS:
            decide_once(event.kind)
        if _finished(simulator, t_max):
            break
    else:
        raise RuntimeError("event limit reached")

    simulator.mark_finished()
    completed = sorted(cid for cid, st in simulator.requests.items() if st.value == "completed")
    rejected = sorted(cid for cid, st in simulator.requests.items() if st.value in {"rejected", "accepted_unfulfilled"})
    commitment_violations = sum(1 for st in simulator.requests.values() if st.value == "accepted_unfulfilled")
    charge_events = sum(1 for rec in simulator.log if rec.kind == "charge_start")
    distance = 0.0
    for rec in simulator.log:
        if rec.kind == "depart":
            origin = rec.data.get("origin")
            dest = rec.data.get("destination")
            if origin and dest:
                try:
                    distance += instance.arc(origin, dest).distance
                except KeyError:
                    pass
    replay = validate_log(instance, simulator.log)
    return RunResult(
        controller=kind.value,
        served=completed,
        rejected=rejected,
        commitment_violations=commitment_violations,
        charge_events=charge_events,
        steps=steps,
        final_feasible_plan=replay.ok,
        first_action_signature=first_sig,
        action_sequence=action_sequence,
        distance=distance,
        optimize_seconds=optimize_seconds,
        log=list(simulator.log),
        replay_ok=replay.ok,
        decision_event_signatures=signatures,
    )


def _served(routes: dict[str, list[Visit]]) -> set[str]:
    out: set[str] = set()
    for visits in routes.values():
        for visit in visits:
            if visit.purpose == "service":
                out.add(visit.node_id)
    return out


def _finished(simulator: FleetSimulator, t_max: float) -> bool:
    open_status = {"announced", "accepted", "deferred", "in_service"}
    if any(status.value in open_status for status in simulator.requests.values()):
        return False
    if simulator.time > t_max + EPS:
        return True
    return all(
        vehicle.status.value == "idle" and vehicle.node == simulator.instance.depot_id
        for vehicle in simulator.vehicles.values()
    )


def compare_controllers(
    instance: Instance,
    *,
    fleet_size: int = 2,
    horizon: float = 4.0,
    releases: list[tuple[str, float]] | None = None,
    forecast: ArrivalForecast | None = None,
    t_max: float | None = None,
) -> dict:
    """Matched Gate 3D comparison under the simulator harness."""
    results: dict[str, RunResult] = {}
    for kind in ControllerKind:
        results[kind.value] = run_sim_dynamic(
            instance,
            kind,
            fleet_size=fleet_size,
            horizon=horizon,
            releases=releases,
            forecast=forecast,
            t_max=t_max,
        )
    rh = results[ControllerKind.RH_OPEN_LOOP.value]
    flex = results[ControllerKind.FLEXIBILITY.value]
    rollout = results[ControllerKind.ROLLOUT.value]
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
                "differs_from_rh": r.first_action_signature != rh.first_action_signature,
                "differs_from_rollout": r.first_action_signature != rollout.first_action_signature,
                "action_hamming_vs_rh": _hamming(r.action_sequence, rh.action_sequence),
                "action_hamming_vs_rollout": _hamming(r.action_sequence, rollout.action_sequence),
                "decision_event_diffs_vs_rh": sum(
                    1 for a, b in zip(r.decision_event_signatures, rh.decision_event_signatures, strict=False) if a != b
                )
                + abs(len(r.decision_event_signatures) - len(rh.decision_event_signatures)),
                "n_steps": len(r.steps),
                "distance": r.distance,
                "optimize_seconds": r.optimize_seconds,
                "replay_ok": r.replay_ok,
            }
            for name, r in results.items()
        },
        "flex_equals_rollout_first": flex.first_action_signature == rollout.first_action_signature,
        "flex_equals_rollout_sequence": flex.action_sequence == rollout.action_sequence,
    }
