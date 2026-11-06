"""Deadline preemption, stale results, and trigger behavior."""

from __future__ import annotations

from time import perf_counter

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.robust.backup import BackupStore, action_id
from safe_time_evrp.robust.certificate import propagate
from safe_time_evrp.robust.controller import SafeTimeController
from safe_time_evrp.robust.episode import run_robust_episode
from safe_time_evrp.robust.supervisor import SolverSupervisor, SupervisorResult
from safe_time_evrp.robust.triggers import TriggerPolicy, classify
from safe_time_evrp.robust.uncertainty import RectangularUncertainty


class _InlineSupervisor:
    """Same-process stand-in used only when the test is not about preemption."""

    def run(self, payload, deadline, state_id, validate) -> SupervisorResult:
        from safe_time_evrp.robust.anytime import improve

        started = perf_counter()
        accepted = None
        count = 0
        for item in improve(
            payload["instance"],
            payload["observation"],
            payload["incumbent"],
            payload["uncertainty"],
            steps=int(payload["steps"]),
            horizon=float(payload["horizon"]),
        ):
            count += 1
            verdict = validate(item)
            if verdict is not None:
                accepted = {"candidate": item, "validation": verdict}
        elapsed = perf_counter() - started
        if elapsed > deadline:
            return SupervisorResult("timeout", elapsed, messages=count)
        return SupervisorResult("ok", elapsed, accepted, messages=count)

    def close(self) -> None:
        return None


def _observation(instance, accepted: tuple[str, ...] = (), released: tuple[str, ...] = ()) -> Observation:
    soc = instance.vehicle_type.battery_capacity
    anchor = Anchor(instance.depot_id, 0.0, soc, 0.0, frozenset())
    view = VehicleView("v1", "idle", instance.depot_id, soc, 0.0, (), anchor, None)
    open_ids = tuple(dict.fromkeys(released + accepted))
    return Observation(0.0, (view,), open_ids, accepted, (), (), (), ())


def test_case_c_hard_timeout_kills_the_worker_and_keeps_the_backup():
    supervisor = SolverSupervisor()
    try:
        result = supervisor.run({"op": "sleep", "seconds": 30}, 0.4, "snap", lambda _message: None)
        assert result.status == "timeout"
        assert result.elapsed < 5.0
        assert supervisor._process is None
        backup = BackupStore(routes={"v1": [Visit("D", "return")]}, version=3)
        assert backup.version == 3
        assert backup.routes["v1"][0].purpose == "return"
    finally:
        supervisor.close()


def test_worker_exception_and_crash_are_explicit():
    supervisor = SolverSupervisor()
    try:
        failed = supervisor.run({"op": "boom"}, 5.0, "snap", lambda _message: None)
        assert failed.status == "error"
        assert "injected" in failed.error
        crashed = supervisor.run({"op": "crash"}, 5.0, "snap", lambda _message: None)
        assert crashed.status == "crash"
        recovered = supervisor.run({"op": "sleep", "seconds": 0.05}, 5.0, "snap", lambda _message: None)
        assert recovered.status == "ok"
    finally:
        supervisor.close()


def test_case_d_stale_action_id_cannot_commit():
    instance = make_reference_instance("easy")
    uncertainty = RectangularUncertainty(1.0, 1.1, 1.0, 1.1)
    observation = _observation(instance, (), ("C1",))
    controller = SafeTimeController(
        instance,
        horizon=200,
        uncertainty=uncertainty,
        policy=TriggerPolicy.EVERY_EVENT,
        deadline=5.0,
        supervisor=_InlineSupervisor(),
        anytime_steps=4,
    )
    proposal = controller.propose(observation, "request_release")
    assert proposal.audit is not None
    assert proposal.audit["replaced_backup"] is True
    moved = Observation(
        observation.time,
        (
            VehicleView(
                "v1",
                "traveling",
                "D",
                observation.vehicles[0].soc,
                0.0,
                (),
                observation.vehicles[0].anchor,
                "C1",
            ),
        ),
        observation.released_open,
        observation.accepted,
        (),
        (),
        (),
        (),
    )
    assert action_id(moved) != action_id(observation)
    assert controller.commit(moved) is False
    assert controller.backup.version == 0
    again = controller.propose(observation, "request_release")
    assert again.audit is not None and again.audit["replaced_backup"] is True
    assert controller.commit(observation) is True
    assert controller.backup.version == 1


def test_case_f_validity_trigger_skips_economic_events_but_not_requests():
    certificate = propagate(
        make_reference_instance("easy"),
        Anchor("D", 0, 50, 0, frozenset()),
        [Visit("C1", "service")],
        RectangularUncertainty(),
    )
    every = [
        classify(TriggerPolicy.EVERY_EVENT, kind, certificate).optimize
        for kind in ("arrive", "service_end", "replan_interval")
    ]
    valid = [
        classify(TriggerPolicy.VALIDITY_AWARE, kind, certificate).optimize
        for kind in ("arrive", "service_end", "replan_interval")
    ]
    assert every == [True, True, True]
    assert valid == [False, False, False]
    prompt = classify(TriggerPolicy.VALIDITY_AWARE, "request_release", certificate)
    assert prompt.optimize is True
    assert prompt.safety_related is True
    hypothesis = classify(TriggerPolicy.VALIDITY_AWARE, "bound_update", certificate)
    assert hypothesis.optimize is True
    delayed = classify(TriggerPolicy.VALIDITY_AWARE, "request_release", certificate, ignore_requests=True)
    assert delayed.optimize is False


def test_case_g_controller_does_not_invent_a_route():
    vehicle = VehicleType(5.0, 10.0, 1.0, 1.0, 1.0, "full")
    instance = build_euclidean_instance(
        "no-route",
        [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 50), 0),
            Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 50), 0),
            Node("A", NodeKind.CUSTOMER, 10, 0, 1, TimeWindow(0, 40), 1),
        ],
        vehicle,
        source_format="synthetic",
        source_name="no-route",
    )
    observation = _observation(instance, ("A",), ("A",))
    controller = SafeTimeController(
        instance,
        50,
        RectangularUncertainty(),
        TriggerPolicy.EVERY_EVENT,
        5.0,
        _InlineSupervisor(),
        anytime_steps=3,
    )
    decision = controller.propose(observation, "initial")
    assert decision.no_feasible_continuation is True
    assert decision.routes["v1"] == []
    assert controller.backup.version == 0


def test_trigger_policies_on_a_shared_episode():
    instance = make_reference_instance("easy")
    uncertainty = RectangularUncertainty(1.0, 1.05, 1.0, 1.05)
    releases = [("C1", 0.0), ("C2", 1.0), ("C3", 2.0)]
    counts = {}
    for policy in (TriggerPolicy.EVERY_EVENT, TriggerPolicy.VALIDITY_AWARE, TriggerPolicy.FIXED_PERIOD):
        controller = SafeTimeController(
            instance,
            200,
            uncertainty,
            policy,
            5.0,
            _InlineSupervisor(),
            anytime_steps=6,
        )
        result = run_robust_episode(
            instance,
            releases,
            controller,
            fleet_size=1,
            t_max=200,
            replan_interval=30,
            advance_plant=True,
        )
        counts[policy.value] = result.optimize_count
        assert result.commitment_failures == 0
        assert result.final_requests["C1"] == "completed"
    assert counts["validity_aware"] < counts["every_event"]
