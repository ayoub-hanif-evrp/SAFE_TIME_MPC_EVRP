import copy

from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.controllers.mpc import EventTriggeredMPC
from safe_time_evrp.models.state import Anchor, LogRecord, Observation, VehicleView
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.optimization.insertion import construct_routes
from safe_time_evrp.validation.replay import validate_log


def _episode():
    instance = make_reference_instance("easy")
    releases = [("C1", 0.0), ("C2", 0.0), ("C3", 30.0)]
    return instance, run_episode(
        instance,
        releases,
        fleet_size=2,
        horizon=200,
        max_replan_interval=40,
        t_max=200,
    )


def test_closed_loop_replays_and_hides_future_requests():
    instance, result = _episode()
    report = validate_log(instance, result.log)
    assert report.ok, report.detail
    assert set(report.announced) == {"C1", "C2", "C3"}
    assert (
        "C3" in report.completed
        or "C3" in report.rejected
        or "C3" in report.accepted_unfulfilled
        or "C3" in report.open_requests
    )
    early = [decision for decision in result.decisions if decision.time < 30]
    assert early
    for decision in early:
        assert "C3" not in decision.newly_accepted
        assert "C3" not in decision.rejected
        assert "C3" not in decision.planned_service
        assert "C3" not in decision.deferred
    departures = [record for record in result.log if record.kind == "depart"]
    assert departures
    # A destination locked at a decision is not replaced before the matching arrival.
    for record in departures:
        later = [
            item
            for item in result.log
            if item.vehicle_id == record.vehicle_id and item.seq > record.seq and item.kind == "depart"
        ]
        arrival = next(
            item
            for item in result.log
            if item.vehicle_id == record.vehicle_id and item.seq > record.seq and item.kind == "arrive"
        )
        interrupting = [item for item in later if item.seq < arrival.seq]
        assert interrupting == []
        assert arrival.data["destination"] == record.data["destination"]
    again = run_episode(
        instance,
        [("C1", 0.0), ("C2", 0.0), ("C3", 30.0)],
        fleet_size=2,
        horizon=200,
        max_replan_interval=40,
        t_max=200,
    )
    assert [record.kind for record in again.log] == [record.kind for record in result.log]
    assert again.final_requests == result.final_requests


def test_observation_has_no_future_field_and_controller_is_a_function_of_it():
    assert "hidden" not in Observation.__dataclass_fields__
    instance = make_reference_instance("easy")
    anchor = Anchor("D", 0.0, 50.0, 0.0, frozenset())
    view = VehicleView("v1", "idle", "D", 50.0, 0.0, (), anchor, None)
    visible = Observation(0.0, (view,), ("C1",), (), (), (), (), ())
    same = Observation(0.0, (view,), ("C1",), (), (), (), (), ())
    first = EventTriggeredMPC(instance, horizon=100).decide(visible, "test")
    second = EventTriggeredMPC(instance, horizon=100).decide(same, "test")
    assert first.planned_service == second.planned_service
    assert "C3" not in first.planned_service


def test_horizon_keeps_an_accepted_commitment():
    instance = make_reference_instance("easy")
    anchor = Anchor("D", 0.0, 50.0, 0.0, frozenset())
    view = VehicleView("v1", "idle", "D", 50.0, 0.0, (), anchor, None)
    observation = Observation(0.0, (view,), ("C3",), ("C3",), (), (), (), ())
    plan = construct_routes(instance, observation, horizon=5.0)
    assert plan.horizon_extended
    assert plan.feasible_commitments
    assert "C3" in plan.planned_service


def test_replay_rejects_corrupted_logs():
    instance = make_reference_instance("easy")
    base = [
        LogRecord(0, 1, "vehicle_init", "v1", {"node": "D", "soc": 50.0, "load": 0.0}),
        LogRecord(0, 2, "request_release", None, {"customer_id": "C1"}),
        LogRecord(
            0,
            3,
            "depart",
            "v1",
            {
                "origin": "D",
                "destination": "C1",
                "energy": instance.arc("D", "C1").energy,
                "travel_time": instance.arc("D", "C1").travel_time,
                "soc": 50.0,
                "load": 1.0,
            },
        ),
        LogRecord(
            instance.arc("D", "C1").travel_time,
            4,
            "arrive",
            "v1",
            {
                "origin": "D",
                "destination": "C1",
                "energy": instance.arc("D", "C1").energy,
                "travel_time": instance.arc("D", "C1").travel_time,
                "soc_before": 50.0,
                "soc": 50.0 - instance.arc("D", "C1").energy,
                "load": 1.0,
            },
        ),
    ]
    # The minimal log has not loaded freight, so service is not required for these mutations.
    negative = copy.deepcopy(base)
    negative[3].data["soc"] = -1.0
    assert validate_log(instance, negative).code == "negative_battery"

    missed = [
        LogRecord(0, 1, "vehicle_init", "v1", {"node": "C1", "soc": 50.0, "load": 1.0}),
        LogRecord(0, 2, "request_release", None, {"customer_id": "C1"}),
        LogRecord(90, 3, "service_start", "v1", {"customer_id": "C1", "load": 0.0, "node": "C1"}),
    ]
    assert validate_log(instance, missed).code == "missed_window"

    duplicate = copy.deepcopy(missed)
    duplicate[2].time = 10.0
    duplicate.append(LogRecord(12, 4, "service_end", "v1", {"customer_id": "C1", "soc": 50.0, "load": 0.0}))
    duplicate.append(LogRecord(14, 5, "service_end", "v1", {"customer_id": "C1", "soc": 50.0, "load": 0.0}))
    assert validate_log(instance, duplicate).code == "duplicate_service"

    early = copy.deepcopy(missed)
    early[1].time = 20.0
    early[2].time = 10.0
    assert validate_log(instance, early).code in {"early_request_access", "time_reversal"}

    charge = [
        LogRecord(0, 1, "vehicle_init", "v1", {"node": "C1", "soc": 10.0, "load": 0.0}),
        LogRecord(
            0,
            2,
            "charge_start",
            "v1",
            {
                "station": "C1",
                "soc": 10.0,
                "target": 50.0,
                "duration": 40.0,
                "load": 0.0,
                "node": "C1",
            },
        ),
    ]
    assert validate_log(instance, charge).code == "impossible_charge"

    interrupted = copy.deepcopy(base)
    interrupted.append(
        LogRecord(
            1,
            5,
            "depart",
            "v1",
            {
                "origin": "D",
                "destination": "C2",
                "energy": instance.arc("D", "C2").energy,
                "travel_time": instance.arc("D", "C2").travel_time,
                "soc": 50.0,
                "load": 0.0,
            },
        )
    )
    assert validate_log(instance, interrupted).code == "interrupted_travel"

    payload = [
        LogRecord(0, 1, "vehicle_init", "v1", {"node": "D", "soc": 50.0, "load": 10.0}),
        LogRecord(
            0,
            2,
            "load_freight",
            "v1",
            {"node": "D", "customers": ["C1"], "load": 11.0, "soc": 50.0},
        ),
    ]
    assert validate_log(instance, payload).code == "excess_payload"

    wrong = copy.deepcopy(base)
    wrong[3].data["destination"] = "S"
    assert validate_log(instance, wrong).code == "wrong_location"

    claimed = validate_log(
        instance,
        base,
        claimed_summary={
            "completed": ["C1"],
            "rejected": [],
            "accepted_unfulfilled": [],
            "open_requests": [],
        },
    )
    assert claimed.code == "denominator_mismatch"
