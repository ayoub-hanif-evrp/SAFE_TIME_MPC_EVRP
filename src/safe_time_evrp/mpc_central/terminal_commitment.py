"""Horizon-end terminal commitment constraint for Commitment-Safe Stochastic MPC.

Stage-0 ``validate_continuation`` checks open-loop coverage *now*.
Terminal commitment checks coverage after simulating to the MPC horizon boundary.

Horizon freeze (Problem A)
--------------------------
When the next plant event is after ``t+H``, we do **not** leave the clock at an
earlier event time. ``freeze_simulator_at_horizon`` advances time to ``t+H`` and
applies a **conservative partial-transition** for noninterruptible actions that
straddle the boundary:

* Travel: deduct energy proportional to elapsed travel time; remain TRAVELING at
  the origin node with a reduced remaining arrive event / anchor.
* Charge: accumulate SoC proportionally; remain CHARGING with updated target
  residual and anchor.
* Service: remain SERVING; completion is guaranteed only at the locked
  ``service_end`` (in_service stays an obligation until then, covered by the lock).

Approximation note: in-transit location is represented as still-at-origin with
proportional SoC drain (Schneider Euclidean model has no continuous path state).
This is conservative for energy (energy is spent) and for reachability of the
destination (still locked). Documented in MPC_TERMINAL_CORRECTNESS_AUDIT.md.

Residual obligations (Problem B)
--------------------------------
Taken from the **simulated terminal observation**, not ``candidate.accepted``:
accepted ∪ in_service − completed, with in_service treated as locked-covered for
Validate's pending set (same semantics as ``validate_continuation``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import FleetSimulator, SimulatorError
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Anchor, Decision, Observation, RequestStatus, Visit
from safe_time_evrp.mpc3c.forecast import ForecastCustomer, augment_instance_for_planning
from safe_time_evrp.mpc_central.causal_plant import B1ValidatedRecourse
from safe_time_evrp.mpc_central.scenario_rollout import (
    announcement_release_time,
    fork_log_for_replay,
    seed_simulator_from_observation,
)
from safe_time_evrp.validation.replay import validate_log

_TRIGGERS = frozenset(
    {"request_release", "arrive", "service_end", "charge_end", "wait_end", "replan", "replan_interval"}
)


class TerminalRejectReason(str, Enum):
    OK = "ok"
    ROLLOUT_FAILED = "rollout_failed"
    TERMINAL_INFEASIBLE = "terminal_infeasible"
    REPLAY_FAILED = "replay_failed"
    BUDGET = "budget"


@dataclass(frozen=True)
class VehicleTerminalView:
    vehicle_id: str
    node: str
    soc: float
    load: float
    status: str
    locked_destination: str | None


@dataclass(frozen=True)
class TerminalState:
    """Public plant snapshot at the MPC horizon boundary."""

    time: float
    vehicles: tuple[VehicleTerminalView, ...]
    residual_obligations: frozenset[str]
    completed: frozenset[str]
    accepted: frozenset[str]
    observation: Observation
    freeze_notes: tuple[str, ...] = ()


@dataclass
class TerminalCommitmentReport:
    ok: bool
    reason: TerminalRejectReason
    terminal_state: TerminalState | None = None
    backup_routes: dict[str, list[Visit]] | None = None
    served: list[str] = field(default_factory=list)
    detail: str = ""
    seconds: float = 0.0


def residual_obligations_from_observation(observation: Observation) -> frozenset[str]:
    """Actual terminal obligations: accepted and in-service, not yet completed."""
    return frozenset((set(observation.accepted) | set(observation.in_service)) - set(observation.completed))


def terminal_state_from_observation(
    observation: Observation,
    *,
    freeze_notes: tuple[str, ...] = (),
) -> TerminalState:
    vehicles = tuple(
        VehicleTerminalView(
            vehicle_id=v.id,
            node=v.node,
            soc=float(v.soc),
            load=float(v.load),
            status=v.status.value if hasattr(v.status, "value") else str(v.status),
            locked_destination=v.locked_destination,
        )
        for v in observation.vehicles
    )
    residual = residual_obligations_from_observation(observation)
    return TerminalState(
        time=float(observation.time),
        vehicles=vehicles,
        residual_obligations=residual,
        completed=frozenset(observation.completed),
        accepted=frozenset(set(observation.accepted) | set(observation.in_service)),
        observation=observation,
        freeze_notes=freeze_notes,
    )


def freeze_simulator_at_horizon(sim: FleetSimulator, horizon_end: float) -> list[str]:
    """Advance simulator clock to ``horizon_end`` with conservative partial locks.

    Returns freeze notes describing applied approximations.
    """
    notes: list[str] = []
    if sim.time >= horizon_end - EPS:
        return notes

    # Cancel / rewrite vehicle events that end after the horizon.
    for vehicle in list(sim.vehicles.values()):
        action = vehicle.action
        if not action:
            continue
        kind = action.get("kind")
        event_id = action.get("event_id")
        if event_id is None:
            continue
        # Find scheduled end time from heap
        end_time = None
        for ev in sim._heap:
            if ev.event_id == event_id and not ev.cancelled:
                end_time = float(ev.time)
                break
        if end_time is None:
            continue
        if end_time <= horizon_end + EPS:
            continue  # will complete at/before H if we were to pop it; freeze only straddlers

        if kind == "travel":
            payload = None
            for ev in sim._heap:
                if ev.event_id == event_id:
                    payload = ev.payload
                    break
            if payload is None:
                continue
            travel_time = float(payload.get("travel_time", 0.0))
            energy = float(payload.get("energy", 0.0))
            soc_before = float(payload.get("soc_before", vehicle.soc))
            destination = payload.get("destination", vehicle.locked_destination)
            origin = payload.get("origin", vehicle.node)
            depart_time = end_time - travel_time
            elapsed = max(0.0, min(travel_time, horizon_end - depart_time))
            frac = 0.0 if travel_time <= EPS else elapsed / travel_time
            spent = frac * energy
            vehicle.soc = max(0.0, soc_before - spent)
            remaining_time = max(0.0, end_time - horizon_end)
            remaining_energy = max(0.0, energy - spent)
            sim.cancel(event_id)
            new_id = sim._push(
                horizon_end + remaining_time,
                0,
                "arrive",
                vehicle_id=vehicle.id,
                payload={
                    "origin": origin,
                    "destination": destination,
                    "energy": remaining_energy,
                    "travel_time": remaining_time,
                    "soc_before": vehicle.soc,
                    "horizon_freeze_partial": True,
                },
            )
            vehicle.action = {"kind": "travel", "event_id": new_id, "destination": destination}
            vehicle.locked_destination = destination
            vehicle.anchor_after = Anchor(
                node=destination,
                time=horizon_end + remaining_time,
                soc=max(0.0, vehicle.soc - remaining_energy),
                load=vehicle.load,
                onboard=frozenset(vehicle.onboard),
            )
            notes.append(f"partial_travel:{vehicle.id}:{origin}->{destination}:frac={frac:.4f}")
            sim._record(
                "horizon_freeze_partial_travel",
                vehicle.id,
                {
                    "origin": origin,
                    "destination": destination,
                    "frac": frac,
                    "soc": vehicle.soc,
                    "remaining_energy": remaining_energy,
                    "remaining_time": remaining_time,
                    "horizon_end": horizon_end,
                },
            )
        elif kind == "charge":
            payload = None
            for ev in sim._heap:
                if ev.event_id == event_id:
                    payload = ev.payload
                    break
            if payload is None or vehicle.anchor_after is None:
                continue
            target = float(payload["target"])
            soc_before = float(payload["soc_before"])
            station = payload.get("station", vehicle.node)
            from safe_time_evrp.environment.energy import NonlinearPiecewiseChargeEnergy

            energy = NonlinearPiecewiseChargeEnergy()
            vt = sim.instance.vehicle_type
            full_duration = energy.charge_duration(
                soc_before, target, vt.inverse_recharge_rate, battery_capacity=vt.battery_capacity
            )
            end_t = float(vehicle.anchor_after.time)
            start_t = end_t - full_duration
            elapsed = max(0.0, min(full_duration, horizon_end - start_t))
            frac = 0.0 if full_duration <= EPS else elapsed / full_duration
            vehicle.soc = soc_before + frac * (target - soc_before)
            remaining = max(0.0, target - vehicle.soc)
            rem_dur = energy.charge_duration(
                vehicle.soc, target, vt.inverse_recharge_rate, battery_capacity=vt.battery_capacity
            ) if remaining > EPS else 0.0
            sim.cancel(event_id)
            new_id = sim._push(
                horizon_end + rem_dur,
                0,
                "charge_end",
                vehicle_id=vehicle.id,
                payload={
                    "station": station,
                    "target": target,
                    "soc_before": vehicle.soc,
                    "horizon_freeze_partial": True,
                },
            )
            vehicle.action = {"kind": "charge", "event_id": new_id, "target": target}
            vehicle.anchor_after = Anchor(
                node=vehicle.node,
                time=horizon_end + rem_dur,
                soc=target,
                load=vehicle.load,
                onboard=frozenset(vehicle.onboard),
            )
            notes.append(f"partial_charge:{vehicle.id}:frac={frac:.4f}:soc={vehicle.soc:.4f}")
            sim._record(
                "horizon_freeze_partial_charge",
                vehicle.id,
                {
                    "station": station,
                    "frac": frac,
                    "soc": vehicle.soc,
                    "target": target,
                    "horizon_end": horizon_end,
                },
            )
        elif kind == "service":
            # Noninterruptible service continues; completion guaranteed only at service_end.
            # Keep SERVING lock; do not mark completed at freeze.
            notes.append(f"partial_service_lock:{vehicle.id}")
            sim._record(
                "horizon_freeze_service_lock",
                vehicle.id,
                {
                    "customer_id": action.get("customer_id"),
                    "horizon_end": horizon_end,
                    "anchor_time": float(vehicle.anchor_after.time) if vehicle.anchor_after else None,
                },
            )
        elif kind == "wait":
            notes.append(f"partial_wait:{vehicle.id}")

    # Drop replan/release events after horizon from consideration by cancelling them
    for ev in list(sim._heap):
        if ev.time > horizon_end + EPS and ev.kind in {"replan_interval", "request_release"}:
            sim.cancel(ev.event_id)

    sim.time = float(horizon_end)
    sim._record("horizon_freeze", None, {"time": horizon_end, "notes": notes})
    notes.append(f"clock={horizon_end}")
    return notes


def verify_terminal_commitment(
    full_instance: Instance,
    terminal_state: TerminalState,
    residual_obligations: frozenset[str],
    *,
    backup_routes: dict[str, list[Visit]] | None = None,
    backup_policy: str = "validate_or_replan",
    energy: NominalLinearEnergy | None = None,
    horizon_probe: float = 50.0,
) -> TerminalCommitmentReport:
    """Independent terminal-set membership test for residual accepted obligations.

    ``backup_policy``:
    - ``validate_or_replan`` (default): try ``backup_routes`` then a reactive replan probe.
    - ``routes_only``: only ``backup_routes`` (no replan probe).
    """
    t0 = perf_counter()
    model = energy or NominalLinearEnergy()
    obs = terminal_state.observation
    # Pending visits: obligations not completed and not already locked in service.
    pending = set(residual_obligations) - set(obs.completed) - set(obs.in_service)
    if not pending:
        return TerminalCommitmentReport(
            ok=True,
            reason=TerminalRejectReason.OK,
            terminal_state=terminal_state,
            backup_routes=backup_routes or {v.id: [] for v in obs.vehicles},
            served=[],
            detail="no_residual_pending_or_locked_in_service",
            seconds=perf_counter() - t0,
        )

    snap = make_public_snapshot(full_instance, obs, horizon=max(horizon_probe, 1.0))
    public = snap.instance

    def _try(routes: dict[str, list[Visit]]) -> TerminalCommitmentReport | None:
        rep = validate_continuation(public, obs, routes, energy=model, require_new=frozenset())
        if rep.ok:
            covered = set(rep.served) | set(obs.in_service)
            if pending <= covered | set(obs.completed):
                return TerminalCommitmentReport(
                    ok=True,
                    reason=TerminalRejectReason.OK,
                    terminal_state=terminal_state,
                    backup_routes={vid: list(vs) for vid, vs in routes.items()},
                    served=list(rep.served),
                    detail="terminal_backup_ok",
                    seconds=perf_counter() - t0,
                )
        return None

    if backup_routes is not None:
        hit = _try(backup_routes)
        if hit is not None:
            return hit
        if backup_policy == "routes_only":
            return TerminalCommitmentReport(
                ok=False,
                reason=TerminalRejectReason.TERMINAL_INFEASIBLE,
                terminal_state=terminal_state,
                detail="backup_routes_failed_routes_only",
                seconds=perf_counter() - t0,
            )

    if backup_policy == "validate_or_replan":
        probe = EventTriggeredMPC(full_instance, horizon=horizon_probe, energy=model).decide(obs, "terminal_probe")
        hit = _try(probe.routes)
        if hit is not None:
            hit.detail = "terminal_replan_probe_ok"
            return hit

    return TerminalCommitmentReport(
        ok=False,
        reason=TerminalRejectReason.TERMINAL_INFEASIBLE,
        terminal_state=terminal_state,
        detail="no_feasible_terminal_suffix",
        seconds=perf_counter() - t0,
    )


def project_to_horizon(
    full_instance: Instance,
    observation: Observation,
    candidate: Decision,
    forecasts: list[ForecastCustomer],
    *,
    horizon: float,
    max_replan_interval: float = 5.0,
    max_events: int = 2_000,
    energy: NominalLinearEnergy | None = None,
    deadline: float | None = None,
) -> tuple[TerminalCommitmentReport, dict[str, list[Visit]] | None]:
    """Simulate candidate + B1 recourse until the MPC horizon; then verify terminal commitment."""
    t0 = perf_counter()
    model = energy or NominalLinearEnergy()
    notes: list[str] = []
    planning = augment_instance_for_planning(full_instance, forecasts)
    try:
        sim = seed_simulator_from_observation(planning, observation, energy=model)
    except SimulatorError as exc:
        return (
            TerminalCommitmentReport(
                ok=False,
                reason=TerminalRejectReason.ROLLOUT_FAILED,
                detail=f"seed_failed:{exc}",
                seconds=perf_counter() - t0,
            ),
            None,
        )

    horizon_end = float(observation.time) + float(horizon)
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
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=list(candidate.planned_service),
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="terminal_project_first",
        locked_destinations={},
        notes=["terminal_project"],
    )
    last_routes = routes
    try:
        sim.apply_decision(first)
    except SimulatorError as exc:
        return (
            TerminalCommitmentReport(
                ok=False,
                reason=TerminalRejectReason.ROLLOUT_FAILED,
                detail=f"dispatch_rejected:{exc}",
                seconds=perf_counter() - t0,
            ),
            None,
        )

    controller = B1ValidatedRecourse(planning, horizon=horizon)
    replan_id = sim.schedule_replan(sim.time + max_replan_interval)
    events = 0
    while events < max_events:
        if deadline is not None and perf_counter() > deadline:
            return (
                TerminalCommitmentReport(
                    ok=False,
                    reason=TerminalRejectReason.BUDGET,
                    detail="deadline_during_horizon_projection",
                    seconds=perf_counter() - t0,
                ),
                last_routes,
            )
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
                return (
                    TerminalCommitmentReport(
                        ok=False,
                        reason=TerminalRejectReason.ROLLOUT_FAILED,
                        detail=f"recourse_rejected:{exc}",
                        seconds=perf_counter() - t0,
                    ),
                    last_routes,
                )
            if replan_id is not None:
                sim.cancel(replan_id)
            replan_id = sim.schedule_replan(sim.time + max_replan_interval)

    freeze_notes = freeze_simulator_at_horizon(sim, horizon_end)
    notes.extend(freeze_notes)
    obs_end = sim.observation()
    assert abs(float(obs_end.time) - horizon_end) <= 1e-6 or float(obs_end.time) >= horizon_end - EPS

    # Replay of fork logs may not understand horizon_freeze markers; filter them for replay.
    replay_log = [
        rec for rec in fork_log_for_replay(sim) if not str(getattr(rec, "kind", "")).startswith("horizon_freeze")
    ]
    report = validate_log(planning, replay_log)
    if not report.ok:
        return (
            TerminalCommitmentReport(
                ok=False,
                reason=TerminalRejectReason.REPLAY_FAILED,
                detail=f"replay:{report.code}:{report.detail}",
                seconds=perf_counter() - t0,
            ),
            last_routes,
        )

    term = terminal_state_from_observation(obs_end, freeze_notes=tuple(freeze_notes))
    # Problem B: residual from simulated terminal state (includes recourse accepts).
    residual = residual_obligations_from_observation(obs_end)
    check = verify_terminal_commitment(
        planning if all(cid in planning.nodes for cid in residual) else full_instance,
        term,
        residual,
        backup_routes=last_routes,
        backup_policy="validate_or_replan",
        energy=model,
    )
    check.seconds = perf_counter() - t0
    if check.terminal_state is None:
        check.terminal_state = term
    if not check.ok and check.reason == TerminalRejectReason.TERMINAL_INFEASIBLE:
        check.detail = (
            f"horizon_end_terminal_infeasible:{check.detail};events={events};"
            f"freeze={';'.join(freeze_notes[:4])};residual={sorted(residual)}"
        )
    return check, last_routes


def stage0_ok_but_terminal_counterexample_state(
    *,
    battery: float = 5.0,
) -> tuple[Instance, Observation, frozenset[str]]:
    """Construct a stranded terminal state that fails verify_terminal_commitment."""
    from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
    from safe_time_evrp.models.state import Anchor, Observation, VehicleView
    from safe_time_evrp.testbed.constructor import make_observation

    vehicle = VehicleType(battery, 10.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 100), 0),
        Node("S0", NodeKind.CHARGER, 0.5, 0, 0, TimeWindow(0, 100), 0),
        Node("C_far", NodeKind.CUSTOMER, 80, 0, 1, TimeWindow(0, 90), 1),
    ]
    inst = build_euclidean_instance(
        "terminal_counterexample",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="terminal_gate2",
        assumptions=("terminal_counterexample",),
    )
    base = make_observation(inst, 1)
    soc = 2.0
    anchor = Anchor("D0", 70.0, soc, 0.0, frozenset())
    v0 = base.vehicles[0]
    stranded = VehicleView(v0.id, "idle", "D0", soc, 0.0, (), anchor, None)
    obs = Observation(
        70.0,
        (stranded,),
        ("C_far",),
        ("C_far",),
        (),
        (),
        (),
        (),
        public_customer_count=1,
    )
    return inst, obs, frozenset({"C_far"})


def build_stage0_feasible_terminal_infeasible_case():
    """Meaningful Gate-2 counterexample: stage-0 Validate OK, projected terminal infeasible.

    Large battery + long feasible open-loop plan from t=0. After dispatching a long
    first charge+wait waste under a **short** horizon, the freeze leaves insufficient
    remaining time/SoC budget for C_far under routes_only backup of an empty suffix.
    """
    from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
    from safe_time_evrp.testbed.constructor import make_observation

    vehicle = VehicleType(200.0, 10.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
        Node("C_far", NodeKind.CUSTOMER, 40, 0, 1, TimeWindow(0, 55), 5),
    ]
    inst = build_euclidean_instance(
        "stage0_ok_terminal_bad",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="terminal_gate2",
        assumptions=("stage0_ok_terminal_bad",),
    )
    obs = make_observation(inst, 1)
    obs = Observation(
        0.0,
        obs.vehicles,
        ("C_far",),
        (),
        (),
        (),
        (),
        (),
        public_customer_count=1,
    )
    # Stage-0 feasible: charge then serve within window.
    stage0_routes = {
        "v0": [Visit("S0", "charge"), Visit("C_far", "service"), Visit("D0", "return")],
    }
    # Bad first-stage for short horizon projection: go charge only (no service in suffix yet
    # after we truncate), accept C_far — stage0 full plan still validates separately.
    bad_first = Decision(
        time=0.0,
        routes={"v0": [Visit("S0", "charge"), Visit("D0", "return")]},
        accepted=["C_far"],
        newly_accepted=["C_far"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["C_far"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="counterexample",
        locked_destinations={},
        notes=["counterexample_charge_only"],
    )
    return inst, obs, stage0_routes, bad_first
