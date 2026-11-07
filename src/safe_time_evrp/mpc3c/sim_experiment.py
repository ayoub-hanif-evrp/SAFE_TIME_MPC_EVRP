"""Simulator-backed closed-loop experiment harness (Gate 3D/3E/4).

Gate 3E contracts:
- Do not terminate while request-release events remain within the evaluation horizon.
- Strip unreleased forecast services, then revalidate cleaned routes before dispatch.
- Admission must not break previously accepted commitments (nominal plant feasibility).
- Never treat accepted customers as rejected.

Gate 4 timing contract (``TimingContract.BLOCKING_WITH_PLANT_ADVANCE``):
- Optimization blocks dispatch decisions while physical time may advance by the
  measured (or forced) optimize duration.
- Events remain chronological on the simulator heap.
- A candidate computed from an outdated plant state is discarded (stale).
- Already dispatched travel/service/charging remain noninterruptible.
- Incumbent routes are retained when new optimization fails the commitment gate.
- This is **not** hard real-time process preemption; do not claim hard deadlines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter

from safe_time_evrp.environment.energy import EPS, NominalLinearEnergy, ScaledNominalEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.environment.simulator import FleetSimulator, SimulatorError
from safe_time_evrp.models.instance import Arc, Instance
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


class TimingContract(str, Enum):
    """Closed-loop computation timing semantics."""

    # Optimize as if instantaneous; plant does not advance during decide (legacy).
    INSTANTANEOUS = "instantaneous"
    # Blocking optimize; plant clock advances by elapsed; intervening events → stale discard.
    BLOCKING_WITH_PLANT_ADVANCE = "blocking_with_plant_advance"


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
    announced: list[str] = field(default_factory=list)
    unannounced_at_cutoff: list[str] = field(default_factory=list)
    accepted_unfulfilled: list[str] = field(default_factory=list)
    t_max: float = 0.0
    executed_first_action_signature: str = ""
    stale_discard_count: int = 0
    plant_time_advanced_during_optimize: bool = False
    timing_contract: str = TimingContract.INSTANTANEOUS.value
    preempted_optimize_count: int = 0
    incumbent_fallback_count: int = 0


def _strip_unreleased(visits: list[Visit], released: set[str], completed: set[str]) -> list[Visit]:
    out: list[Visit] = []
    for visit in visits:
        if visit.purpose == "service" and visit.node_id not in released and visit.node_id not in completed:
            continue
        out.append(visit)
    return out


def _served(routes: dict[str, list[Visit]]) -> set[str]:
    out: set[str] = set()
    for visits in routes.values():
        for visit in visits:
            if visit.purpose == "service":
                out.add(visit.node_id)
    return out


def _assignment_has_duplicates(routes: dict[str, list[Visit]]) -> bool:
    seen: set[str] = set()
    for visits in routes.values():
        for visit in visits:
            if visit.purpose != "service":
                continue
            if visit.node_id in seen:
                return True
            seen.add(visit.node_id)
    return False


def _with_scaled_travel_times(instance: Instance, time_scale: float) -> Instance:
    if abs(time_scale - 1.0) <= 1e-12:
        return instance
    arcs = {
        key: Arc(
            origin=arc.origin,
            destination=arc.destination,
            distance=arc.distance,
            travel_time=arc.travel_time * time_scale,
            energy=arc.energy,
            distance_definition=arc.distance_definition,
            distance_km=arc.distance_km,
            travel_time_h=(arc.travel_time_h * time_scale) if arc.travel_time_h is not None else None,
        )
        for key, arc in instance.arcs.items()
    }
    return Instance(
        name=instance.name,
        nodes=instance.nodes,
        arcs=arcs,
        vehicle_type=instance.vehicle_type,
        depot_id=instance.depot_id,
        source_format=instance.source_format,
        source_name=instance.source_name,
        assumptions=instance.assumptions + (f"time_scale={time_scale}",),
        station_capacity=instance.station_capacity,
        metadata=dict(instance.metadata),
    )


def _routes_cover_commitments(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    accepted: list[str],
    *,
    energy_scale: float = 1.0,
    time_scale: float = 1.0,
) -> bool:
    """Commitment feasibility under explicitly budgeted energy/time scales.

    Default scales (1,1) are nominal. This is an admission gate, not a recursive
    feasibility theorem under arbitrary disturbances. Duplicate service assignments
    across vehicles are rejected.
    """
    if _assignment_has_duplicates(routes):
        return False
    model = NominalLinearEnergy() if abs(energy_scale - 1.0) <= 1e-12 else ScaledNominalEnergy(energy_scale)
    plant = _with_scaled_travel_times(instance, time_scale)
    pending = {
        c
        for c in accepted
        if c not in observation.completed and c not in observation.in_service and c not in observation.rejected
    }
    covered: set[str] = set()
    for vehicle in observation.vehicles:
        result = evaluate_route(plant, vehicle.anchor, routes.get(vehicle.id, []), model)
        if not result.feasible:
            return False
        covered.update(result.served)
    return pending <= covered


def robust_routes_cover_commitments(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
    accepted: list[str],
    *,
    energy_scale: float = 1.1,
    time_scale: float = 1.1,
) -> bool:
    """Budgeted robust cover check (explicit scales; not a disturbance adversary)."""
    return _routes_cover_commitments(
        instance,
        observation,
        routes,
        accepted,
        energy_scale=energy_scale,
        time_scale=time_scale,
    )


def _clean_and_revalidate(
    instance: Instance,
    observation: Observation,
    routes: dict[str, list[Visit]],
) -> dict[str, list[Visit]]:
    """Strip unreleased forecast services and independently revalidate each vehicle route."""
    model = NominalLinearEnergy()
    q = instance.vehicle_type.battery_capacity
    released = set(observation.released_open) | set(observation.accepted) | set(observation.in_service)
    completed = set(observation.completed)
    applied: dict[str, list[Visit]] = {}
    for vehicle in observation.vehicles:
        raw = routes.get(vehicle.id, [])
        cleaned = _strip_unreleased(raw, released, completed)
        suffix = dispatch_suffix(cleaned, observation, vehicle.node, vehicle.soc, q)
        if vehicle.status in {"traveling", "serving", "charging"}:
            applied[vehicle.id] = suffix
            continue
        result = evaluate_route(instance, vehicle.anchor, suffix, model)
        # Keep the cleaned suffix (not evaluate_route's rewritten visit list) when feasible.
        applied[vehicle.id] = suffix if result.feasible else []
    return applied


def _to_decision(
    observation: Observation,
    routes: dict[str, list[Visit]],
    *,
    newly_accepted: list[str],
    rejected: list[str],
    deferred: list[str],
    accepted: list[str],
    planned_service: list[str],
    optimize_seconds: float,
    trigger: str,
    notes: list[str],
    fallback_used: bool = False,
    no_feasible_continuation: bool = False,
) -> Decision:
    locked = {vehicle.id: vehicle.locked_destination for vehicle in observation.vehicles}
    return Decision(
        time=observation.time,
        routes=routes,
        accepted=list(accepted),
        newly_accepted=list(newly_accepted),
        rejected=list(rejected),
        deferred=list(deferred),
        fallback_used=fallback_used,
        no_feasible_continuation=no_feasible_continuation,
        horizon_extended=False,
        planned_service=list(planned_service),
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=optimize_seconds,
        trigger=trigger,
        locked_destinations=locked,
        notes=list(notes),
    )


def _action_sig(routes: dict[str, list[Visit]]) -> str:
    parts = []
    for vid in sorted(routes):
        visits = routes[vid]
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


def _pending_release_within(simulator: FleetSimulator, t_max: float) -> bool:
    """True if a future request_release remains scheduled at or before t_max."""
    for event in list(simulator._heap):
        if event.cancelled or event.event_id in simulator._cancelled:
            continue
        if event.kind == "request_release" and event.time <= t_max + EPS:
            return True
    return False


def _finished(simulator: FleetSimulator, t_max: float) -> bool:
    if _pending_release_within(simulator, t_max):
        return False
    open_status = {"announced", "accepted", "deferred", "in_service"}
    if any(status.value in open_status for status in simulator.requests.values()):
        return False
    if simulator.time + EPS < t_max:
        # Still inside evaluation horizon with no open work and no pending releases.
        # Allow finish only when fleet is idle at depot (no more plant events needed).
        nxt = simulator.next_event_time()
        if nxt is not None and nxt <= t_max + EPS:
            return False
    return all(
        vehicle.status.value == "idle" and vehicle.node == simulator.instance.depot_id
        for vehicle in simulator.vehicles.values()
    )


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
    advance_plant_during_optimize: bool | None = None,
    timing_contract: TimingContract | None = None,
    forced_optimize_seconds: float | None = None,
) -> RunResult:
    """Closed-loop episode through ``FleetSimulator``.

    ``forced_optimize_seconds`` is a test hook that replaces measured wall time when
    exercising the plant-time / stale-discard contract.

    For any claim of real-time or computation-aware performance, pass
    ``timing_contract=TimingContract.BLOCKING_WITH_PLANT_ADVANCE`` (or
    ``advance_plant_during_optimize=True``). Instantaneous optimize is allowed only
    as a non-realtime diagnostic.
    """
    if timing_contract is None:
        if advance_plant_during_optimize is True:
            timing_contract = TimingContract.BLOCKING_WITH_PLANT_ADVANCE
        elif advance_plant_during_optimize is False:
            timing_contract = TimingContract.INSTANTANEOUS
        else:
            timing_contract = TimingContract.INSTANTANEOUS
    advance = timing_contract is TimingContract.BLOCKING_WITH_PLANT_ADVANCE

    model = energy or NominalLinearEnergy()
    if releases is None:
        releases = [(cid, float(instance.node(cid).window.ready)) for cid in instance.customer_ids()]
    if t_max is None:
        t_max = max((rt for _, rt in releases), default=0.0)
        t_max = max(t_max, max(instance.node(cid).window.due for cid in instance.customer_ids())) + 50.0
    if max_replan_interval is None:
        max_replan_interval = max(horizon, 1.0)

    release_map = {cid: float(rt) for cid, rt in releases}
    simulator = FleetSimulator(instance, fleet_size, energy=model, disturbance=disturbance)
    for customer_id, release_time in releases:
        simulator.schedule_release(customer_id, release_time)

    steps: list[StepLog] = []
    action_sequence: list[tuple[float, str, str | None, str | None]] = []
    signatures: list[str] = []
    optimize_seconds = 0.0
    replan_id: int | None = None
    same_time = 0
    last_decision_time = -1.0
    first_sig = ""
    executed_first_sig = ""
    stale_discard_count = 0
    plant_time_advanced = False
    incumbent_fallback_count = 0
    incumbent_routes: dict[str, list[Visit]] = {f"v{i + 1}": [] for i in range(fleet_size)}

    def decide_once(trigger: str) -> None:
        nonlocal optimize_seconds, replan_id, same_time, last_decision_time
        nonlocal first_sig, executed_first_sig, incumbent_routes, stale_discard_count
        nonlocal plant_time_advanced, incumbent_fallback_count
        if abs(simulator.time - last_decision_time) <= EPS:
            same_time += 1
        else:
            same_time = 0
            last_decision_time = simulator.time
        if same_time > 32:
            raise RuntimeError("decision loop did not advance time")

        observation = simulator.observation()
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
        # Use outer-scope test hook when set (do not shadow with a local parameter).
        elapsed = float(forced_optimize_seconds) if forced_optimize_seconds is not None else (perf_counter() - wall)
        optimize_seconds += elapsed

        if advance and elapsed > 0:
            # Blocking + plant advance: intervening events make the candidate stale —
            # discard without applying; locked plant actions continue. Optimize work
            # is accounted in optimize_seconds even when discarded.
            start_time = simulator.time
            nxt = simulator.next_event_time()
            if nxt is not None and start_time + elapsed > nxt + EPS:
                stale_discard_count += 1
                return
            simulator.time = start_time + elapsed
            plant_time_advanced = True

        observation = simulator.observation()
        cleaned = _clean_and_revalidate(instance, observation, ctrl.routes)

        # Proposed accepts: released customers appearing in cleaned routes.
        truly_released = set(observation.released_open)
        planned_released = _served(cleaned) & truly_released
        proposed_accepted = list(observation.accepted)
        newly = sorted(c for c in planned_released if c not in observation.accepted and c not in observation.in_service)
        for cid in newly:
            if cid not in proposed_accepted:
                proposed_accepted.append(cid)

        # Commitment gate: new admissions must keep all accepted feasible.
        notes = list(ctrl.notes)
        fallback = False
        no_cont = False
        if not _routes_cover_commitments(instance, observation, cleaned, proposed_accepted):
            # Refuse new admissions; try incumbent cleaned routes for current accepted.
            newly = []
            proposed_accepted = list(observation.accepted)
            if incumbent_routes and _routes_cover_commitments(
                instance, observation, incumbent_routes, proposed_accepted
            ):
                cleaned = {
                    vid: dispatch_suffix(
                        list(visits),
                        observation,
                        next(v for v in observation.vehicles if v.id == vid).node,
                        next(v for v in observation.vehicles if v.id == vid).soc,
                        instance.vehicle_type.battery_capacity,
                    )
                    for vid, visits in incumbent_routes.items()
                    if any(v.id == vid for v in observation.vehicles)
                }
                fallback = True
                incumbent_fallback_count += 1
                notes.append("commitment_gate_kept_incumbent")
            elif _routes_cover_commitments(instance, observation, cleaned, proposed_accepted):
                notes.append("commitment_gate_refused_new_accepts")
            else:
                no_cont = True
                notes.append("no_feasible_commitment_continuation")
                # Safe returns for idle vehicles; do not reject accepted.
                cleaned = {}
                for vehicle in observation.vehicles:
                    if vehicle.status in {"traveling", "serving", "charging"}:
                        cleaned[vehicle.id] = list(incumbent_routes.get(vehicle.id, []))
                    else:
                        cleaned[vehicle.id] = [Visit(instance.depot_id, "return")]

        deferred = [
            c
            for c in observation.released_open
            if c not in proposed_accepted
            and c not in observation.completed
            and c not in observation.in_service
            and (
                instance.node(c).window.ready > observation.time + 1e-9
                or instance.node(c).window.ready > observation.time + horizon
            )
        ]
        # Never reject already-accepted commitments.
        rejected = [
            c
            for c in observation.released_open
            if c not in proposed_accepted
            and c not in observation.completed
            and c not in observation.in_service
            and c not in deferred
            and c not in planned_released
            and c not in observation.accepted
        ]

        decision = _to_decision(
            observation,
            cleaned,
            newly_accepted=newly,
            rejected=rejected,
            deferred=deferred,
            accepted=proposed_accepted,
            planned_service=sorted(_served(cleaned) & truly_released),
            optimize_seconds=elapsed,
            trigger=trigger,
            notes=notes,
            fallback_used=fallback,
            no_feasible_continuation=no_cont,
        )
        if _routes_cover_commitments(instance, observation, cleaned, proposed_accepted):
            incumbent_routes = {vid: list(visits) for vid, visits in cleaned.items()}

        if not first_sig:
            first_sig = _action_sig(ctrl.routes)
        if not executed_first_sig:
            executed_first_sig = _action_sig(cleaned)
        signatures.append(_action_sig(cleaned))
        for vid in sorted(cleaned):
            visits = cleaned[vid]
            if visits:
                first = visits[0]
                action_sequence.append((observation.time, vid, first.node_id, first.purpose))
            else:
                action_sequence.append((observation.time, vid, None, None))
        steps.append(
            StepLog(
                observation.time,
                kind.value,
                {vid: (visits[0].node_id if visits else None) for vid, visits in cleaned.items()},
                sum(1 for s in simulator.requests.values() if s.value == "completed"),
                list(notes),
                trigger=trigger,
            )
        )
        try:
            simulator.apply_decision(decision)
        except SimulatorError as exc:
            notes.append(f"plant_rejected_dispatch:{exc}")
            safe_routes = {
                vehicle.id: (
                    list(incumbent_routes.get(vehicle.id, []))
                    if vehicle.status in {"traveling", "serving", "charging"}
                    else []
                )
                for vehicle in observation.vehicles
            }
            safe = _to_decision(
                observation,
                safe_routes,
                newly_accepted=[],
                rejected=[],
                deferred=[
                    c
                    for c in observation.released_open
                    if c not in observation.accepted and c not in observation.completed
                ],
                accepted=list(observation.accepted),
                planned_service=[],
                optimize_seconds=elapsed,
                trigger=trigger,
                notes=notes,
                fallback_used=True,
                no_feasible_continuation=True,
            )
            simulator.apply_decision(safe)
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
    # Eligible = released by cutoff.
    eligible = sorted(cid for cid, rt in release_map.items() if rt <= t_max + EPS)
    unannounced = sorted(cid for cid in instance.customer_ids() if cid not in eligible)
    completed = sorted(cid for cid, st in simulator.requests.items() if st.value == "completed")
    rejected = sorted(cid for cid, st in simulator.requests.items() if st.value == "rejected")
    accepted_unfulfilled = sorted(cid for cid, st in simulator.requests.items() if st.value == "accepted_unfulfilled")
    # Also count accepted still open at cutoff as unfulfilled for reporting.
    still_open_accepted = sorted(
        cid
        for cid, st in simulator.requests.items()
        if st.value in {"accepted", "in_service", "deferred"} and cid in observation_accepted_safe(simulator)
    )
    accepted_unfulfilled = sorted(set(accepted_unfulfilled) | set(still_open_accepted))
    commitment_violations = len(accepted_unfulfilled)
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
        announced=eligible,
        unannounced_at_cutoff=unannounced,
        accepted_unfulfilled=accepted_unfulfilled,
        t_max=t_max,
        executed_first_action_signature=executed_first_sig,
        stale_discard_count=stale_discard_count,
        plant_time_advanced_during_optimize=plant_time_advanced,
        timing_contract=timing_contract.value,
        preempted_optimize_count=stale_discard_count,
        incumbent_fallback_count=incumbent_fallback_count,
    )


def observation_accepted_safe(simulator: FleetSimulator) -> set[str]:
    return {cid for cid, st in simulator.requests.items() if st.value in {"accepted", "in_service", "deferred"}}


def compare_controllers(
    instance: Instance,
    *,
    fleet_size: int = 2,
    horizon: float = 4.0,
    releases: list[tuple[str, float]] | None = None,
    forecast: ArrivalForecast | None = None,
    t_max: float | None = None,
) -> dict:
    """Matched comparison under the simulator harness."""
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
                "n_announced_eligible": len(r.announced),
                "service_rate": (len(r.served) / len(r.announced)) if r.announced else 0.0,
                "rejected": r.rejected,
                "commitment_violations": r.commitment_violations,
                "accepted_unfulfilled": r.accepted_unfulfilled,
                "charge_events": r.charge_events,
                "first_action_signature": r.first_action_signature,
                "executed_first_action_signature": r.executed_first_action_signature,
                "differs_from_rh": r.executed_first_action_signature != rh.executed_first_action_signature,
                "differs_from_rollout": r.executed_first_action_signature != rollout.executed_first_action_signature,
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
        "flex_equals_rollout_first": flex.executed_first_action_signature == rollout.executed_first_action_signature,
        "flex_equals_rollout_sequence": flex.action_sequence == rollout.action_sequence,
    }
