"""Causal closed-loop scenario rollouts from a public observation.

Preserves the observation clock and remaining noninterruptible actions. Busy
vehicles are **not** teleported to future anchors. Terminal scoring distinguishes
feasible residual obligations from genuine commitment breaks.
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


def is_quiescent(observation: Observation) -> bool:
    """True iff no vehicle is mid-travel / mid-service / mid-charge."""
    for v in observation.vehicles:
        st = v.status if isinstance(v.status, VehicleStatus) else VehicleStatus(v.status)
        if st in _BUSY:
            return False
    return True


def announcement_release_time(fc: ForecastCustomer, now: float) -> float:
    """Schedule plant release from announcement time (not service-window ready)."""
    announce = getattr(fc, "announcement_time", None)
    if announce is None:
        announce = fc.ready_time
    return max(float(announce), float(now))


def seed_simulator_from_observation(
    instance: Instance,
    observation: Observation,
    *,
    energy: NominalLinearEnergy | None = None,
    require_quiescent: bool = False,
) -> FleetSimulator:
    """Build a plant fork matching the observation clock and physical vehicle state.

    Busy vehicles keep their current node/SOC and a restored completion event at
    ``anchor.time``. Candidates applied while busy only update suffixes (plant rule).
    """
    if require_quiescent and not is_quiescent(observation):
        raise SimulatorError("predictive comparison restricted to quiescent decision epochs")

    fleet_size = len(observation.vehicles)
    sim = FleetSimulator(instance, fleet_size=fleet_size, energy=energy)
    # Drop misleading t=0 init records; fork begins at the observation epoch.
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

        sim._record(
            "fork_seed",
            vehicle.id,
            {
                "node": vehicle.node,
                "soc": vehicle.soc,
                "load": vehicle.load,
                "status": status.value,
                "locked_destination": view.locked_destination,
                "anchor_time": view.anchor.time,
                "anchor_node": view.anchor.node,
            },
        )

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
                event_id = sim._push(
                    view.anchor.time,
                    0,
                    "charge_end",
                    vehicle_id=view.id,
                    payload={
                        "station": view.node,
                        "target": target,
                        "soc_before": view.soc,
                    },
                )
                vehicle.action = {"kind": "charge", "event_id": event_id, "target": target}
                vehicle.locked_destination = view.node
        elif status is VehicleStatus.WAITING:
            vehicle.status = VehicleStatus.WAITING
            # Waiting is interruptible; no forced completion event.
        else:
            vehicle.status = VehicleStatus.IDLE
            vehicle.locked_destination = None

    known_customers = set(instance.customer_ids())
    for cid in known_customers:
        if sim.requests.get(cid) is RequestStatus.IN_SERVICE:
            continue
        sim.requests[cid] = RequestStatus.HIDDEN
    for cid in observation.completed:
        if cid in sim.requests:
            sim.requests[cid] = RequestStatus.COMPLETED
    for cid in observation.rejected:
        if cid in sim.requests:
            sim.requests[cid] = RequestStatus.REJECTED
    for cid in observation.in_service:
        if cid in sim.requests and sim.requests[cid] is not RequestStatus.IN_SERVICE:
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

    for vehicle in sim.vehicles.values():
        if vehicle.status is VehicleStatus.IDLE:
            sim._record(
                "vehicle_init",
                vehicle.id,
                {"node": vehicle.node, "soc": vehicle.soc, "load": vehicle.load, "fork": True},
            )
    return sim


def _terminal_score(
    planning: Instance,
    sim: FleetSimulator,
    observation: Observation,
    *,
    last_routes: dict | None,
) -> tuple[float, tuple[str, ...], tuple[str, ...], tuple[str, ...], list[str]]:
    """Score at prediction horizon without false AU penalties for feasible residuals."""
    notes: list[str] = []
    completed = tuple(sorted(cid for cid, st in sim.requests.items() if st.value == "completed"))
    pending = sorted(
        cid for cid, st in sim.requests.items() if st.value in {"accepted", "in_service", "accepted_unfulfilled"}
    )
    # Prefer not calling mark_finished — it forces AU.
    obs_end = sim.observation()
    routes = last_routes or {v.id: [] for v in obs_end.vehicles}
    # Try last routes, then insertion residual probe.
    snap = make_public_snapshot(planning, obs_end, horizon=max(1.0, planning.vehicle_type.battery_capacity))
    public = snap.instance
    report = validate_continuation(public, obs_end, routes, require_new=frozenset())
    if not report.ok:
        probe = EventTriggeredMPC(planning, horizon=50.0).decide(obs_end, "horizon_residual_probe")
        report = validate_continuation(public, obs_end, probe.routes, require_new=frozenset())
        routes = probe.routes
    residual_ok = report.ok
    residual_feasible: tuple[str, ...]
    genuine_au: tuple[str, ...]
    if residual_ok:
        residual_feasible = tuple(pending)
        genuine_au = ()
        notes.append("horizon_end_residual_feasible")
    else:
        residual_feasible = ()
        genuine_au = tuple(pending)
        notes.append("horizon_end_residual_infeasible")
        notes.extend(report.reasons[:2])
    dist = executed_distance_from_log(planning, sim.log)
    value = SERVICE_REWARD * len(completed) - UNFULFILLED_PENALTY * len(genuine_au) - DISTANCE_PENALTY * dist
    # Small credit for feasible unfinished work (not a fake service reward).
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
    """Causal closed-loop value of ``candidate`` under one forecast scenario."""
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
    # Replay against planning instance; fork_seed records are ignored by physics checks if present.
    report = validate_log(planning, [rec for rec in sim.log if rec.kind != "fork_seed"])
    if not report.ok:
        notes.append("replay_failed")
        if report.detail:
            notes.append(report.detail[:120])
        # Invalid physical rollouts must not look like high-value wins.
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
    )


def expected_rollout_value(
    full_instance: Instance,
    observation: Observation,
    candidate: Decision,
    scenario_forecasts: list[list[ForecastCustomer]],
    *,
    horizon: float,
    max_scenarios: int | None = None,
    **kwargs,
) -> tuple[float, tuple[ScenarioRolloutScore, ...]]:
    """Mean causal value over forecast scenarios (equal weight; CRN-friendly index order)."""
    scenarios = scenario_forecasts if max_scenarios is None else scenario_forecasts[:max_scenarios]
    if not scenarios:
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
            notes=("no_forecast_nominal_only",),
            quiescent_epoch=is_quiescent(observation),
        )
        return value, (score,)
    scores = tuple(
        rollout_candidate(full_instance, observation, candidate, fcs, horizon=horizon, **kwargs) for fcs in scenarios
    )
    # Drop invalid replay scores from the mean (treat as -inf contribution → exclude).
    valid = [s for s in scores if s.replay_ok]
    if not valid:
        return -1e9, scores
    return sum(s.value for s in valid) / len(valid), scores
