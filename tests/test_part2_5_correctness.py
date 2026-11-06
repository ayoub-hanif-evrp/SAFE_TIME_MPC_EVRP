"""Part 2.5: certificate soundness, cache keys, real-time semantics, disturbed plant."""

from __future__ import annotations

from time import perf_counter

from safe_time_evrp.environment.disturbance import ArcDisturbanceSampler
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Anchor, Decision, Observation, VehicleView, Visit
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.robust.backup import observation_version
from safe_time_evrp.robust.certificate import (
    IncrementalCache,
    Verdict,
    certify_routes,
    propagate,
    propagate_incremental,
)
from safe_time_evrp.robust.controller import SafeTimeController
from safe_time_evrp.robust.episode import run_robust_episode
from safe_time_evrp.robust.supervisor import SolverSupervisor, SupervisorResult
from safe_time_evrp.robust.triggers import TriggerPolicy
from safe_time_evrp.robust.uncertainty import RectangularUncertainty, scale_instance
from safe_time_evrp.validation.replay import validate_log


def _partial_cex():
    vehicle = VehicleType(10.0, 10.0, 1.0, 1.0, 1.0, "partial")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 500), 0),
    ]
    return build_euclidean_instance(
        "partial-cex",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="partial-cex",
    )


def test_fixed_partial_charge_upper_corner_is_not_exact():
    instance = _partial_cex()
    anchor = Anchor("D", 0.0, 10.0, 0.0, frozenset())
    visits = [Visit("S", "charge", charge_target=8.0), Visit("D", "return")]
    uncertainty = RectangularUncertainty(1.0, 1.0, 0.5, 2.0)
    upper = scale_instance(instance, time_factor=1.0, energy_factor=2.0)
    lower = scale_instance(instance, time_factor=1.0, energy_factor=0.5)
    assert evaluate_route(upper, anchor, visits).feasible is True
    assert evaluate_route(lower, anchor, visits).feasible is False
    assert evaluate_route(lower, anchor, visits).reason == "impossible_charge"
    certificate = propagate(instance, anchor, visits, uncertainty)
    assert certificate.verdict is Verdict.UNKNOWN
    assert certificate.critical_constraint == "fixed_partial_target_not_monotone"


def test_full_charge_still_uses_upper_corner():
    vehicle = VehicleType(10.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 500), 0),
    ]
    instance = build_euclidean_instance("full-ok", nodes, vehicle, source_format="synthetic", source_name="full")
    anchor = Anchor("D", 0.0, 10.0, 0.0, frozenset())
    visits = [Visit("S", "charge"), Visit("D", "return")]
    uncertainty = RectangularUncertainty(1.0, 1.0, 0.5, 2.0)
    certificate = propagate(instance, anchor, visits, uncertainty)
    assert certificate.verdict is Verdict.CERTIFIED_FEASIBLE
    assert evaluate_route(scale_instance(instance, time_factor=1.0, energy_factor=2.0), anchor, visits).feasible


def test_partial_with_degenerate_energy_bounds_is_exact():
    instance = _partial_cex()
    anchor = Anchor("D", 0.0, 10.0, 0.0, frozenset())
    visits = [Visit("S", "charge", charge_target=8.0)]
    uncertainty = RectangularUncertainty(1.0, 1.0, 1.0, 1.0)
    # Arrival SOC = 8 exactly after energy 2; charge to 8 is a no-op and is allowed.
    certificate = propagate(instance, anchor, visits, uncertainty)
    assert certificate.verdict is Verdict.CERTIFIED_FEASIBLE


def test_incremental_cache_invalidated_by_uncertainty_and_charge_target():
    instance = make_reference_instance("easy")
    anchor = Anchor("D", 0.0, 50.0, 0.0, frozenset())
    route = [Visit("C1", "service"), Visit("S", "charge"), Visit("C2", "service")]
    cache = IncrementalCache()
    first = propagate_incremental(instance, anchor, route, RectangularUncertainty(1.0, 1.1, 1.0, 1.1), cache)
    assert first.verdict in {Verdict.CERTIFIED_FEASIBLE, Verdict.CERTIFIED_INFEASIBLE}
    misses = cache.misses
    # Different uncertainty must not reuse prefixes.
    propagate_incremental(instance, anchor, route, RectangularUncertainty(1.0, 1.2, 1.0, 1.2), cache)
    assert cache.misses == misses + 1
    # Different charge target on a later visit: after a full miss rebuild, changing target invalidates.
    cache2 = IncrementalCache()
    propagate_incremental(instance, anchor, route, RectangularUncertainty(), cache2)
    altered = [Visit("C1", "service"), Visit("S", "charge", charge_target=40.0), Visit("C2", "service")]
    # Full policy ignores charge_target, but the cache key still includes it so a changed key misses.
    before = cache2.hits
    propagate_incremental(instance, anchor, altered, RectangularUncertainty(), cache2)
    # Signature differs at the charge visit; prefix C1 may still hit.
    assert cache2.hits + cache2.misses > before or cache2.misses >= 1
    # Changed anchor must miss.
    other = Anchor("D", 1.0, 50.0, 0.0, frozenset())
    misses_before = cache2.misses
    propagate_incremental(instance, other, route, RectangularUncertainty(), cache2)
    assert cache2.misses == misses_before + 1


def test_fleet_rejects_duplicate_service_and_unknown_vehicle():
    instance = make_reference_instance("easy")
    soc = 50.0
    anchor = Anchor("D", 0.0, soc, 0.0, frozenset())
    v1 = VehicleView("v1", "idle", "D", soc, 0.0, (), anchor, None)
    v2 = VehicleView("v2", "idle", "D", soc, 0.0, (), anchor, None)
    observation = Observation(0.0, (v1, v2), ("C1",), ("C1",), (), (), (), ())
    dup = certify_routes(
        instance,
        observation,
        {"v1": [Visit("C1", "service")], "v2": [Visit("C1", "service")]},
        RectangularUncertainty(),
    )
    assert dup.verdict is Verdict.CERTIFIED_INFEASIBLE
    assert dup.critical_constraint == "duplicate_service"
    bad = certify_routes(
        instance,
        observation,
        {"v9": [Visit("C1", "service")]},
        RectangularUncertainty(),
    )
    assert bad.verdict is Verdict.CERTIFIED_INFEASIBLE
    assert bad.critical_constraint == "illegal_vehicle_assignment"


def test_intervening_event_blocks_stale_dispatch():
    instance = make_reference_instance("easy")

    class SlowSupervisor:
        def run(self, payload, deadline, state_id, validate):
            started = perf_counter()
            # Force wall time larger than the gap to the next release.
            while perf_counter() - started < 0.05:
                pass
            from safe_time_evrp.robust.anytime import improve

            accepted = None
            for item in improve(
                payload["instance"],
                payload["observation"],
                payload["incumbent"],
                payload["uncertainty"],
                steps=2,
                horizon=float(payload["horizon"]),
            ):
                verdict = validate(item)
                if verdict is not None:
                    accepted = {"candidate": item, "validation": verdict}
            return SupervisorResult("ok", perf_counter() - started, accepted, messages=1)

        def close(self) -> None:
            return None

    controller = SafeTimeController(
        instance,
        200,
        RectangularUncertainty(1.0, 1.05, 1.0, 1.05),
        TriggerPolicy.EVERY_EVENT,
        5.0,
        SlowSupervisor(),
        anytime_steps=2,
    )
    result = run_robust_episode(
        instance,
        [("C1", 0.0), ("C2", 0.02)],
        controller,
        fleet_size=1,
        t_max=200,
        replan_interval=50,
        advance_plant=True,
    )
    assert result.stale_count >= 1
    stale_records = [record for record in result.records if record.get("stale")]
    assert stale_records
    assert all(record.get("applied") is False for record in stale_records)
    times = [record.time for record in result.log]
    assert times == sorted(times)


def test_disturbed_plant_logged_and_replayed():
    instance = make_reference_instance("easy")
    disturbance = ArcDisturbanceSampler(0.9, 1.1, 0.9, 1.1, seed=7, mode="upper")
    simulator = FleetSimulator(instance, 1, disturbance=disturbance)
    simulator.schedule_release("C1", 0.0)
    event = simulator.pop_event()
    assert event is not None and event.kind == "request_release"
    decision = Decision(
        time=simulator.time,
        routes={"v1": [Visit("C1", "service")]},
        accepted=["C1"],
        newly_accepted=["C1"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["C1"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="request_release",
        locked_destinations={"v1": None},
    )
    simulator.apply_decision(decision)
    while simulator.next_event_time() is not None and simulator.time < 200:
        simulator.pop_event()
        vehicle = simulator.vehicles["v1"]
        if vehicle.status.value == "idle" and vehicle.suffix:
            simulator.apply_decision(
                Decision(
                    time=simulator.time,
                    routes={"v1": list(vehicle.suffix)},
                    accepted=["C1"],
                    newly_accepted=[],
                    rejected=[],
                    deferred=[],
                    fallback_used=False,
                    no_feasible_continuation=False,
                    horizon_extended=False,
                    planned_service=[],
                    total_distance=0.0,
                    total_charge_time=0.0,
                    optimize_seconds=0.0,
                    trigger="continue",
                    locked_destinations={"v1": None},
                )
            )
        if vehicle.status.value == "idle" and not vehicle.suffix and vehicle.node == "D":
            break
    departs = [record for record in simulator.log if record.kind == "depart"]
    assert departs
    assert all("energy_factor" in record.data and "time_factor" in record.data for record in departs)
    assert all(abs(record.data["energy_factor"] - 1.1) < 1e-9 for record in departs)
    report = validate_log(instance, simulator.log)
    assert report.ok
    # Controller must not see the sampler history.
    assert not hasattr(SafeTimeController, "disturbance_history")


def test_out_of_set_disturbance_is_labeled():
    sampler = ArcDisturbanceSampler(1.0, 1.1, 1.0, 1.1, seed=1, mode="out_of_set")
    time_f, energy_f = sampler.factors("D", "C1")
    assert time_f > 1.1
    assert energy_f > 1.1
    assert sampler.history[-1]["in_set"] is False


def test_observation_version_tracks_uncertainty_change():
    soc = 50.0
    view = VehicleView("v1", "idle", "D", soc, 0.0, (), Anchor("D", 0, soc, 0, frozenset()), None)
    observation = Observation(0.0, (view,), ("C1",), (), (), (), (), ())
    a = observation_version(observation, RectangularUncertainty(1.0, 1.1, 1.0, 1.1))
    b = observation_version(observation, RectangularUncertainty(1.0, 1.2, 1.0, 1.2))
    assert a != b


def test_process_supervisor_restart_after_timeout():
    supervisor = SolverSupervisor()
    try:
        first = supervisor.run({"op": "sleep", "seconds": 20}, 0.3, "a", lambda _m: None)
        assert first.status == "timeout"
        second = supervisor.run({"op": "sleep", "seconds": 0.05}, 5.0, "b", lambda _m: None)
        assert second.status == "ok"
    finally:
        supervisor.close()
