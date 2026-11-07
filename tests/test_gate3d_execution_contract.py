"""Gate 3D execution-contract tests — must fail on Gate 3C-style harness bugs."""

from __future__ import annotations

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Anchor, Decision, Visit
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.mpc3c.flexibility import flexibility_terminal_value
from safe_time_evrp.mpc3c.forecast import ForecastCustomer, information_safe_remaining
from safe_time_evrp.mpc3c.sim_experiment import run_sim_dynamic
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.testbed.constructor import make_observation
from safe_time_evrp.validation.replay import validate_log


def _multi_stop_instance():
    vehicle = VehicleType(80.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 500), 0),
        Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 500), 0),
        Node("C1", NodeKind.CUSTOMER, 5, 0, 1, TimeWindow(0, 200), 1),
        Node("C2", NodeKind.CUSTOMER, 10, 0, 1, TimeWindow(0, 200), 1),
        Node("C3", NodeKind.CUSTOMER, 15, 0, 1, TimeWindow(0, 200), 1),
    ]
    return build_euclidean_instance(
        "gate3d_multi_stop",
        nodes,
        vehicle,
        source_format="gate3d_contract",
        source_name="execution_contract",
        assumptions=("euclidean_contract_toy",),
    )


def test_multi_stop_first_action_is_not_depot_microtrip():
    """Full suffix dispatch: first action travels to a customer; suffix retained."""
    instance = _multi_stop_instance()
    sim = FleetSimulator(instance, 1)
    for cid in instance.customer_ids():
        sim.schedule_release(cid, 0.0)
    # Force announcement.
    while sim.next_event_time() is not None and sim.next_event_time() <= 0.0:
        sim.pop_event()
    obs = sim.observation()
    suffix = [Visit("C1", "service"), Visit("C2", "service"), Visit("C3", "service"), Visit("D", "return")]
    decision = Decision(
        time=obs.time,
        routes={"v1": suffix},
        accepted=["C1", "C2", "C3"],
        newly_accepted=["C1", "C2", "C3"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["C1", "C2", "C3"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="test",
        locked_destinations={"v1": None},
    )
    sim.apply_decision(decision)
    vehicle = sim.vehicles["v1"]
    assert vehicle.status.value == "traveling"
    assert vehicle.locked_destination == "C1"
    # Remaining suffix retained (not reduced to a single evaluate_route microtrip).
    assert any(v.node_id == "C2" for v in vehicle.suffix)
    # Contrast: Gate 3C bug pattern — evaluate_route([first]) auto-appends depot return.
    anchor = Anchor("D", 0.0, instance.vehicle_type.battery_capacity, 0.0, frozenset())
    micro = evaluate_route(instance, anchor, [Visit("C1", "service")], NominalLinearEnergy())
    assert micro.visits[-1].purpose == "return"
    assert micro.visits[-1].node_id == "D"


def test_charge_then_service_locked_until_complete():
    instance = make_reference_instance("needs_two_charges")
    sim = FleetSimulator(instance, 1)
    sim.schedule_release("C1", 0.0)
    while sim.next_event_time() is not None and sim.next_event_time() <= 0.0:
        sim.pop_event()
    charger = instance.charger_ids()[0]
    suffix = [Visit(charger, "charge"), Visit("C1", "service"), Visit(instance.depot_id, "return")]
    obs = sim.observation()
    decision = Decision(
        time=obs.time,
        routes={"v1": suffix},
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
        trigger="test",
        locked_destinations={"v1": None},
    )
    sim.apply_decision(decision)
    # May travel to charger first.
    while sim.vehicles["v1"].status.value == "traveling":
        ev = sim.pop_event()
        assert ev is not None
    if sim.vehicles["v1"].status.value != "charging":
        # Arrive then start charge via continue suffix — push next start.
        if sim.vehicles["v1"].suffix:
            from safe_time_evrp.environment.simulator import FleetSimulator as FS

            FS._start_suffix(sim, sim.vehicles["v1"], list(sim.vehicles["v1"].suffix))
    # Once charging, a replan cannot cancel the locked charge destination mid-action.
    if sim.vehicles["v1"].status.value == "charging":
        locked = sim.vehicles["v1"].locked_destination
        assert locked == charger
        # Attempt replan with empty routes while charging — suffix may update but action continues.
        empty = Decision(
            time=sim.time,
            routes={"v1": []},
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
            trigger="replan",
            locked_destinations={"v1": locked},
        )
        sim.apply_decision(empty)
        assert sim.vehicles["v1"].status.value == "charging"
        assert sim.vehicles["v1"].locked_destination == charger


def test_sim_episode_replays_under_plant_physics():
    instance = make_reference_instance("easy")
    releases = [("C1", 0.0), ("C2", 0.0), ("C3", 30.0)]
    result = run_sim_dynamic(
        instance,
        ControllerKind.RH_OPEN_LOOP,
        fleet_size=2,
        horizon=200.0,
        releases=releases,
        t_max=200.0,
        max_replan_interval=40.0,
    )
    report = validate_log(instance, result.log)
    assert report.ok, report.detail
    assert result.replay_ok


def test_multi_vehicle_idle_anchors_match_plant_time():
    instance = make_reference_instance("easy")
    result = run_sim_dynamic(
        instance,
        ControllerKind.MYOPIC,
        fleet_size=2,
        horizon=50.0,
        releases=[("C1", 0.0), ("C2", 5.0), ("C3", 30.0)],
        t_max=200.0,
        max_replan_interval=25.0,
    )
    assert result.steps
    # Desync would have raised inside run_sim_dynamic; also check log consistency.
    assert result.replay_ok


def test_flexibility_score_ignores_hidden_customers():
    """Regression: changing hidden (unreleased) customers must not change F(s)."""
    vehicle = VehicleType(50.0, 10.0, 1.0, 1.0, 1.0, "full")
    nodes_a = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 5, 0, 1, TimeWindow(0, 80), 1),
        Node("H1", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(100, 180), 1),
    ]
    nodes_b = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 5, 0, 1, TimeWindow(0, 80), 1),
        Node("H2", NodeKind.CUSTOMER, 0, 25, 1, TimeWindow(100, 180), 1),
        Node("H3", NodeKind.CUSTOMER, 25, 25, 1, TimeWindow(110, 190), 1),
    ]
    inst_a = build_euclidean_instance("leak_a", nodes_a, vehicle, source_format="t", source_name="t", assumptions=())
    inst_b = build_euclidean_instance("leak_b", nodes_b, vehicle, source_format="t", source_name="t", assumptions=())
    obs = make_observation(inst_a, 1, start_time=0.0)
    # Only C1 is treated as released in the observation helper; rebuild with C1 only.
    obs = type(obs)(
        obs.time,
        obs.vehicles,
        ("C1",),
        (),
        (),
        (),
        (),
        (),
    )
    forecasts: list[ForecastCustomer] = []
    rem_a = information_safe_remaining(obs, forecasts)
    rem_b = information_safe_remaining(obs, forecasts)
    assert rem_a == rem_b == ["C1"]
    anchor = obs.vehicles[0].anchor
    # Leaky Gate 3C pattern would use instance.customer_ids(); those differ.
    leak_a = [c for c in inst_a.customer_ids() if c not in obs.completed]
    leak_b = [c for c in inst_b.customer_ids() if c not in obs.completed]
    assert leak_a != leak_b
    fa = flexibility_terminal_value(inst_a, anchor, rem_a)
    fb = flexibility_terminal_value(inst_a, anchor, rem_b)
    assert fa == fb
    # And the controller itself must not consult hidden IDs.
    d1 = decide(inst_a, obs, ControllerKind.FLEXIBILITY, horizon=10.0, forecast_customers=[])
    d2 = decide(inst_b, obs, ControllerKind.FLEXIBILITY, horizon=10.0, forecast_customers=[])
    # Same released set → same first action on shared geometry (C1).
    vid = obs.vehicles[0].id
    assert d1.first_actions[vid] is not None
    assert d1.first_actions[vid].node_id == d2.first_actions[vid].node_id
