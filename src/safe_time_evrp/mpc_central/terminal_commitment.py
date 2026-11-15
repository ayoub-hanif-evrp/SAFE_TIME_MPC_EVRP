"""Horizon-end terminal commitment constraint for Commitment-Safe Stochastic MPC.

This module is intentionally separate from stage-0 ``validate_continuation``.
Stage-0 checks whether a full open-loop plan covers obligations *now*.
Terminal commitment checks whether, after simulating the candidate through the
MPC prediction horizon under a scenario, the *terminal state* still admits a
feasible continuation (or certified backup suffix) for residual obligations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter

from safe_time_evrp.commitment_safe_mpc.continuation_validate import validate_continuation
from safe_time_evrp.commitment_safe_mpc.public_snapshot import make_public_snapshot
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy
from safe_time_evrp.environment.simulator import SimulatorError
from safe_time_evrp.models.instance import Instance
from safe_time_evrp.models.state import Decision, Observation, RequestStatus, Visit
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


@dataclass
class TerminalCommitmentReport:
    ok: bool
    reason: TerminalRejectReason
    terminal_state: TerminalState | None = None
    backup_routes: dict[str, list[Visit]] | None = None
    served: list[str] = field(default_factory=list)
    detail: str = ""
    seconds: float = 0.0


def terminal_state_from_observation(observation: Observation) -> TerminalState:
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
    return TerminalState(
        time=float(observation.time),
        vehicles=vehicles,
        residual_obligations=frozenset(
            set(observation.accepted) - set(observation.completed) - set(observation.in_service)
        ),
        completed=frozenset(observation.completed),
        accepted=frozenset(observation.accepted),
        observation=observation,
    )


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
    # Obligations that still need a future service visit.
    pending = set(residual_obligations) - set(obs.completed) - set(obs.in_service)
    if not pending:
        return TerminalCommitmentReport(
            ok=True,
            reason=TerminalRejectReason.OK,
            terminal_state=terminal_state,
            backup_routes=backup_routes or {v.id: [] for v in obs.vehicles},
            served=[],
            detail="no_residual_pending",
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
    """Simulate candidate + B1 recourse until the MPC horizon; then verify terminal commitment.

    Returns ``(report, last_routes)``. Rejection reasons distinguish rollout vs terminal.
    """
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

    # Freeze clock at horizon for terminal accounting if plant is still earlier.
    obs_end = sim.observation()
    if obs_end.time + EPS < horizon_end:
        # Observation is whatever the plant reached; terminal time is max(plant, H) conceptually,
        # but we evaluate feasibility from the actual reached public state (cannot invent motion).
        pass

    report = validate_log(planning, fork_log_for_replay(sim))
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

    term = terminal_state_from_observation(obs_end)
    # Residual obligations = previously accepted (incl. new accepts in candidate) not completed.
    residual = frozenset(set(candidate.accepted) - set(obs_end.completed) - set(obs_end.in_service))
    # Also include accepted still in_service as covered by lock, not residual pending visits.
    check = verify_terminal_commitment(
        planning if all(cid in planning.nodes for cid in residual) else full_instance,
        term,
        residual,
        backup_routes=last_routes,
        backup_policy="validate_or_replan",
        energy=model,
    )
    check.seconds = perf_counter() - t0
    if not check.ok and check.reason == TerminalRejectReason.TERMINAL_INFEASIBLE:
        check.detail = f"horizon_end_terminal_infeasible:{check.detail};events={events}"
    return check, last_routes


def stage0_ok_but_terminal_counterexample_state(
    *,
    battery: float = 5.0,
) -> tuple[Instance, Observation, frozenset[str]]:
    """Construct a terminal state that fails verify_terminal_commitment.

    Far customer, almost-empty battery, no charger on the only remaining path budget.
    Used by Gate-2 tests — not a stage-0 plan.
    """
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
    # Vehicle stranded with tiny SoC, far from C_far, window closing.
    soc = 2.0
    anchor = Anchor("D0", 70.0, soc, 0.0, frozenset())
    v0 = base.vehicles[0]
    stranded = VehicleView(
        v0.id,
        "idle",
        "D0",
        soc,
        0.0,
        (),
        anchor,
        None,
    )
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
