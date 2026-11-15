"""Causal closed-loop scenario rollouts from a public observation.

Snapshot-to-fork contract
-------------------------
The fork starts at the observation clock with public vehicle/request state.
For independent replay, the fork log must include:

* ``vehicle_init`` for every vehicle at the snapshot state
* ``request_release`` for every *already public* customer (announced/accepted/
  completed/rejected/deferred/in_service), timestamped at the snapshot time
  with ``source=decision_epoch_snapshot`` — this reconstructs information
  history for the fork suffix; it does **not** invent hidden future releases
* For busy vehicles: matching ``depart`` / ``service_start`` / ``charge_start``
  evidence for the remaining noninterruptible action

Accessing a still-HIDDEN customer continues to fail replay and plant physics.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import FleetSimulator, SimulatorError
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import (
    Anchor,
    Decision,
    Observation,
    RequestStatus,
    VehicleStatus,
)
from safe_time_evrp.mpc3c.forecast import ForecastCustomer, augment_instance_for_planning
from safe_time_evrp.mpc_central.causal_plant import (
    DISTANCE_PENALTY,
    SERVICE_REWARD,
    UNFULFILLED_PENALTY,
    B1ValidatedRecourse,
)
from safe_time_evrp.validation.replay import validate_log

_TRIGGERS = frozenset(
    {"request_release", "arrive", "service_end", "charge_end", "wait_end", "replan", "replan_interval"}
)
_BUSY = frozenset({VehicleStatus.TRAVELING, VehicleStatus.SERVING, VehicleStatus.CHARGING})


@dataclass(frozen=True)
class ScenarioRolloutScore:
    value: float
    completed: tuple[str, ...]
    accepted_unfulfilled: tuple[str, ...]
    residual_feasible_pending: tuple[str, ...]
    executed_distance: float
    replay_ok: bool
    events: int
    notes: tuple[str, ...]
    quiescent_epoch: bool = True
    replay_code: str = "ok"
    replay_detail: str = ""


def is_quiescent(observation: Observation) -> bool:
    for v in observation.vehicles:
        st = v.status if isinstance(v.status, VehicleStatus) else VehicleStatus(v.status)
        if st in _BUSY:
            return False
    return True


def announcement_release_time(fc: ForecastCustomer, now: float) -> float:
    announce = getattr(fc, "announcement_time", None)
    if announce is None:
        announce = fc.ready_time
    return max(float(announce), float(now))


def _public_customer_ids(observation: Observation) -> set[str]:
    return (
        set(observation.released_open)
        | set(observation.accepted)
        | set(observation.completed)
        | set(observation.rejected)
        | set(observation.in_service)
        | set(observation.deferred)
    )


def seed_simulator_from_observation(
    instance: Instance,
    observation: Observation,
    *,
    energy: NominalLinearEnergy | None = None,
    require_quiescent: bool = False,
) -> FleetSimulator:
    """Build a plant fork matching the observation clock with replayable history prefix."""
    if require_quiescent and not is_quiescent(observation):
        raise SimulatorError("predictive comparison restricted to quiescent decision epochs")

    fleet_size = len(observation.vehicles)
    sim = FleetSimulator(instance, fleet_size=fleet_size, energy=energy)
    sim.log.clear()
    sim._log_seq = 0
    sim.time = float(observation.time)

    if any(v.id != f"v{i + 1}" for i, v in enumerate(observation.vehicles)):
        new_vehicles = {}
        for i, view in enumerate(observation.vehicles):
            old = sim.vehicles[f"v{i + 1}"]
            old.id = view.id
            new_vehicles[view.id] = old
        sim.vehicles = new_vehicles

    # 1) vehicle_init at snapshot state (required by replay).
    for view in observation.vehicles:
        vehicle = sim.vehicles[view.id]
        status = view.status if isinstance(view.status, VehicleStatus) else VehicleStatus(view.status)
        vehicle.node = view.node
        vehicle.soc = view.soc
        vehicle.load = view.load
        vehicle.onboard = set(view.onboard)
        vehicle.suffix = []
        vehicle.wait_customer = None
        vehicle.locked_destination = view.locked_destination
        vehicle.anchor_after = None
        vehicle.action = None
        vehicle.status = VehicleStatus.IDLE  # temporary; busy restored below
        sim._record(
            "vehicle_init",
            vehicle.id,
            {
                "node": vehicle.node,
                "soc": vehicle.soc,
                "load": vehicle.load,
                "snapshot": True,
                "observed_status": status.value,
            },
        )

    # 2) Reconstruct public request_release history for already-known customers.
    # Timestamp = observation.time (decision-epoch snapshot). Hidden customers stay absent.
    for cid in sorted(_public_customer_ids(observation)):
        if cid not in sim.requests:
            continue
        sim.release_time[cid] = float(observation.time)
        sim._record(
            "request_release",
            None,
            {
                "customer_id": cid,
                "time": float(observation.time),
                "source": "decision_epoch_snapshot",
            },
        )

    # 3) Apply public request statuses.
    for cid in instance.customer_ids():
        sim.requests[cid] = RequestStatus.HIDDEN
    for cid in observation.completed:
        if cid in sim.requests:
            sim.requests[cid] = RequestStatus.COMPLETED
    for cid in observation.rejected:
        if cid in sim.requests:
            sim.requests[cid] = RequestStatus.REJECTED
    for cid in observation.in_service:
        if cid in sim.requests:
            sim.requests[cid] = RequestStatus.IN_SERVICE
    for cid in observation.accepted:
        if cid in sim.requests and sim.requests[cid] is RequestStatus.HIDDEN:
            sim.requests[cid] = RequestStatus.ACCEPTED
    for cid in observation.deferred:
        if cid in sim.requests and sim.requests[cid] is RequestStatus.HIDDEN:
            sim.requests[cid] = RequestStatus.DEFERRED
    for cid in observation.released_open:
        if cid in sim.requests and sim.requests[cid] is RequestStatus.HIDDEN:
            sim.requests[cid] = RequestStatus.ANNOUNCED

    # 4) Restore busy noninterruptible actions with matching log evidence.
    for view in observation.vehicles:
        vehicle = sim.vehicles[view.id]
        status = view.status if isinstance(view.status, VehicleStatus) else VehicleStatus(view.status)
        if status in _BUSY and view.anchor.time > observation.time + EPS:
            vehicle.status = status
            vehicle.anchor_after = Anchor(
                node=view.anchor.node,
                time=view.anchor.time,
                soc=view.anchor.soc,
                load=view.anchor.load,
                onboard=frozenset(view.anchor.onboard),
            )
            if status is VehicleStatus.TRAVELING:
                dest = view.locked_destination or view.anchor.node
                energy_left = max(0.0, float(view.soc) - float(view.anchor.soc))
                travel_left = max(0.0, float(view.anchor.time) - float(observation.time))
                sim._record(
                    "depart",
                    vehicle.id,
                    {
                        "origin": view.node,
                        "destination": dest,
                        "soc": view.soc,
                        "load": view.load,
                        "onboard": sorted(view.onboard),
                        "travel_time": travel_left,
                        "energy": energy_left,
                        "time_factor": 1.0,
                        "energy_factor": 1.0,
                        "snapshot_remainder": True,
                    },
                )
                event_id = sim._push(
                    view.anchor.time,
                    0,
                    "arrive",
                    vehicle_id=view.id,
                    payload={
                        "origin": view.node,
                        "destination": dest,
                        "energy": energy_left,
                        "travel_time": travel_left,
                        "soc_before": view.soc,
                        "time_factor": 1.0,
                        "energy_factor": 1.0,
                    },
                )
                vehicle.action = {"kind": "travel", "event_id": event_id, "destination": dest}
                vehicle.locked_destination = dest
            elif status is VehicleStatus.SERVING:
                cid = view.locked_destination
                if cid is None:
                    raise SimulatorError("serving vehicle missing locked customer")
                sim.requests[cid] = RequestStatus.IN_SERVICE
                sim._record(
                    "service_start",
                    vehicle.id,
                    {
                        "customer_id": cid,
                        "node": view.node,
                        "soc": view.soc,
                        "load": view.load,
                        "service_time": max(0.0, view.anchor.time - observation.time),
                        "window_ready": 0.0,
                        "window_due": 1e9,
                        "snapshot_remainder": True,
                    },
                )
                event_id = sim._push(
                    view.anchor.time,
                    0,
                    "service_end",
                    vehicle_id=view.id,
                    payload={"customer_id": cid, "demand": 0.0},
                )
                vehicle.action = {"kind": "service", "event_id": event_id, "customer_id": cid}
            elif status is VehicleStatus.CHARGING:
                target = view.anchor.soc
                duration = max(0.0, view.anchor.time - observation.time)
                sim._record(
                    "charge_start",
                    vehicle.id,
                    {
                        "station": view.node,
                        "soc": view.soc,
                        "target": target,
                        "duration": duration,
                        "load": view.load,
                        "node": view.node,
                        "snapshot_remainder": True,
                    },
                )
                event_id = sim._push(
                    view.anchor.time,
                    0,
                    "charge_end",
                    vehicle_id=view.id,
                    payload={"station": view.node, "target": target, "soc_before": view.soc},
                )
                vehicle.action = {"kind": "charge", "event_id": event_id, "target": target}
                vehicle.locked_destination = view.node
        elif status is VehicleStatus.WAITING:
            vehicle.status = VehicleStatus.WAITING
        else:
            vehicle.status = VehicleStatus.IDLE
            vehicle.locked_destination = None
    return sim


def fork_log_for_replay(sim: FleetSimulator):
    """Log view for independent replay (drop diagnostic-only markers if any)."""
    return [rec for rec in sim.log if rec.kind != "fork_seed"]


def _terminal_score(
    planning: Instance,
    sim: FleetSimulator,
    observation: Observation,
    *,
    last_routes: dict | None,
) -> tuple[float, tuple[str, ...], tuple[str, ...], tuple[str, ...], list[str]]:
    notes: list[str] = []
    completed = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "completed"))
    pending = sorted(
        cid for cid, st in sim.requests.items() if st.value in {"accepted", "in_service", "accepted_unfulfilled"}
    )
    obs_end = sim.observation()
    routes = last_routes or {v.id: [] for v in obs_end.vehicles}
    snap = make_public_snapshot(planning, obs_end, horizon=max(1.0, planning.vehicle_type.battery_capacity))
    public = snap.instance
    report = validate_continuation(public, obs_end, routes, require_new=frozenset())
    if not report.ok:
        probe = EventTriggeredMPC(planning, horizon=50.0).decide(obs_end, "horizon_residual_probe")
        report = validate_continuation(public, obs_end, probe.routes, require_new=frozenset())
        routes = probe.routes
    if report.ok:
        residual_feasible = tuple(pending)
        genuine_au: tuple[str, ...] = ()
        notes.append("horizon_end_residual_feasible")
    else:
        residual_feasible = ()
        genuine_au = tuple(pending)
        notes.append("horizon_end_residual_infeasible")
        notes.extend(report.reasons[:2])
    dist = executed_distance_from_log(planning, sim.log)
    value = SERVICE_REWARD * len(completed) - UNFULFILLED_PENALTY * len(genuine_au) - DISTANCE_PENALTY * dist
    value += 10.0 * len(residual_feasible)
    notes.append(f"executed_distance={dist:.6f}")
    return value, completed, genuine_au, residual_feasible, notes


def rollout_candidate(
    full_instance: Instance,
    observation: Observation,
    candidate: Decision,
    forecasts: list[ForecastCustomer],
    *,
    horizon: float,
    t_max: float | None = None,
    max_replan_interval: float = 5.0,
    max_events: int = 2_000,
    energy: NominalLinearEnergy | None = None,
    require_quiescent: bool = False,
) -> ScenarioRolloutScore:
    model = energy or NominalLinearEnergy()
    notes: list[str] = ["causal_scenario_rollout", "recourse=b1_validated"]
    quiescent = is_quiescent(observation)
    notes.append("quiescent_epoch" if quiescent else "busy_epoch_restored_actions")
    planning = augment_instance_for_planning(full_instance, forecasts)
    try:
        sim = seed_simulator_from_observation(planning, observation, energy=model, require_quiescent=require_quiescent)
    except SimulatorError as exc:
        return ScenarioRolloutScore(
            value=-1e9,
            completed=(),
            accepted_unfulfilled=tuple(observation.accepted),
            residual_feasible_pending=(),
            executed_distance=0.0,
            replay_ok=False,
            events=0,
            notes=("seed_failed", str(exc)),
            quiescent_epoch=quiescent,
            replay_code="seed_failed",
            replay_detail=str(exc),
        )

    horizon_end = observation.time + (t_max if t_max is not None else horizon)

    for fc in forecasts:
        if fc.customer_id not in sim.requests:
            continue
        release_t = announcement_release_time(fc, observation.time)
        try:
            sim.schedule_release(fc.customer_id, release_t)
        except Exception as exc:  # noqa: BLE001
            notes.append(f"release_skip:{fc.customer_id}:{exc}")

    routes = {vid: [vis for vis in visits if vis.node_id in planning.nodes] for vid, visits in candidate.routes.items()}
    first = Decision(
        time=observation.time,
        routes=routes,
        accepted=list(candidate.accepted),
        newly_accepted=[c for c in candidate.newly_accepted if c in planning.nodes],
        rejected=[c for c in candidate.rejected if c in planning.nodes],
        deferred=list(candidate.deferred),
        fallback_used=candidate.fallback_used,
        no_feasible_continuation=candidate.no_feasible_continuation,
        horizon_extended=False,
        planned_service=list(candidate.planned_service),
        total_distance=candidate.total_distance,
        total_charge_time=candidate.total_charge_time,
        optimize_seconds=0.0,
        trigger="scenario_first",
        locked_destinations={},
        notes=["scenario_first_action"],
    )
    last_routes = routes
    try:
        sim.apply_decision(first)
    except SimulatorError as exc:
        notes.append(f"dispatch_rejected:{exc}")
        return ScenarioRolloutScore(
            value=-1e9,
            completed=(),
            accepted_unfulfilled=tuple(observation.accepted),
            residual_feasible_pending=(),
            executed_distance=0.0,
            replay_ok=False,
            events=0,
            notes=tuple(notes),
            quiescent_epoch=quiescent,
            replay_code="dispatch_rejected",
            replay_detail=str(exc),
        )

    controller = B1ValidatedRecourse(planning, horizon=horizon)
    replan_id = sim.schedule_replan(sim.time + max_replan_interval)
    events = 0
    while events < max_events:
        nxt = sim.next_event_time()
        if nxt is None or nxt > horizon_end + EPS:
            break
        event = sim.pop_event()
        events += 1
        if event is None:
            break
        if event.kind in _TRIGGERS:
            decision = controller.decide(sim.observation(), event.kind)
            hidden = {cid for cid, st in sim.requests.items() if st is RequestStatus.HIDDEN}
            decision.routes = {
                vid: [vis for vis in visits if vis.node_id not in hidden] for vid, visits in decision.routes.items()
            }
            try:
                sim.apply_decision(decision)
                last_routes = decision.routes
            except SimulatorError as exc:
                notes.append(f"recourse_rejected:{exc}")
                break
            if replan_id is not None:
                sim.cancel(replan_id)
            replan_id = sim.schedule_replan(sim.time + max_replan_interval)

    value, completed, genuine_au, residual_feasible, term_notes = _terminal_score(
        planning, sim, observation, last_routes=last_routes
    )
    notes.extend(term_notes)
    notes.append(f"events={events}")
    report = validate_log(planning, fork_log_for_replay(sim))
    if not report.ok:
        notes.append("replay_failed")
        if report.detail:
            notes.append(report.detail[:120])
        value = -1e9
    return ScenarioRolloutScore(
        value=value,
        completed=completed,
        accepted_unfulfilled=genuine_au,
        residual_feasible_pending=residual_feasible,
        executed_distance=next(
            (float(n.split("=", 1)[1]) for n in notes if n.startswith("executed_distance=")),
            0.0,
        ),
        replay_ok=report.ok,
        events=events,
        notes=tuple(notes),
        quiescent_epoch=quiescent,
        replay_code=report.code,
        replay_detail=report.detail,
    )


def greedy_nominal_value(
    full_instance: Instance,
    observation: Observation,
    candidate: Decision,
    *,
    horizon: float,
) -> tuple[float, tuple[ScenarioRolloutScore, ...]]:
    """Legacy nominal continuation score (NOT the causal no-forecast ablation).

    Preserved as the named ``greedy_nominal`` baseline. Do not use this as the
    default meaning of ``use_forecast=False``.
    """
    public = make_public_snapshot(full_instance, observation, horizon).instance
    rep = validate_continuation(
        public,
        observation,
        candidate.routes,
        require_new=frozenset(candidate.newly_accepted),
    )
    value = (100.0 * len(rep.served) - rep.distance) if rep.ok else -1e9
    score = ScenarioRolloutScore(
        value=value,
        completed=tuple(rep.served),
        accepted_unfulfilled=(),
        residual_feasible_pending=(),
        executed_distance=rep.distance,
        replay_ok=rep.ok,
        events=0,
        notes=("greedy_nominal_continuation",),
        quiescent_epoch=is_quiescent(observation),
        replay_code="ok" if rep.ok else "nominal_invalid",
        replay_detail="" if rep.ok else ";".join(rep.reasons[:2]),
    )
    return value, (score,)


def expected_rollout_value(
    full_instance: Instance,
    observation: Observation,
    candidate: Decision,
    scenario_forecasts: list[list[ForecastCustomer]],
    *,
    horizon: float,
    max_scenarios: int | None = None,
    scoring_mode: str = "causal",
    **kwargs,
) -> tuple[float, tuple[ScenarioRolloutScore, ...]]:
    """Mean causal value — **fail closed** if any scenario replay is invalid.

    ``scoring_mode``:
    - ``causal`` (default): always use ``rollout_candidate``. An empty forecast list
      means *no future announcements*, scored with the same causal objective as
      non-empty forecast scenarios.
    - ``greedy_nominal``: legacy ``100 * served - distance`` continuation heuristic.
    """
    if scoring_mode == "greedy_nominal":
        return greedy_nominal_value(full_instance, observation, candidate, horizon=horizon)
    if scoring_mode != "causal":
        raise ValueError(f"unknown scoring_mode={scoring_mode!r}")
    scenarios = list(scenario_forecasts if max_scenarios is None else scenario_forecasts[:max_scenarios])
    # Fair no-forecast ablation: one empty-future scenario through the same causal path.
    if not scenarios:
        scenarios = [[]]
    scores = tuple(
        rollout_candidate(full_instance, observation, candidate, fcs, horizon=horizon, **kwargs) for fcs in scenarios
    )
    # Fail closed: any invalid scenario invalidates the candidate ranking value.
    if any(not s.replay_ok for s in scores):
        return -1e9, scores
    return sum(s.value for s in scores) / len(scores), scores
