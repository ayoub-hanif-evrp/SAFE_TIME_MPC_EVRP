"""Phase B: authoritative FleetSimulator plant + independent replay."""

from __future__ import annotations

import copy

from safe_time_evrp.commitment_safe_mpc.phase_b_demo import run_phase_b_demo, write_phase_b_artifact
from safe_time_evrp.commitment_safe_mpc.plant import AUTHORITATIVE_PLANT, observation_hides_future
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.models.state import LogRecord, Observation
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.validation.replay import validate_log


def test_authoritative_plant_is_fleet_simulator():
    assert "FleetSimulator" in AUTHORITATIVE_PLANT
    obs = Observation(0.0, (), (), (), (), (), (), ())
    assert observation_hides_future(obs)


def test_phase_b_demo_meets_all_completion_criteria(tmp_path):
    result, log, report = run_phase_b_demo()
    assert all(result.criteria.values()), result.notes
    assert report.ok
    assert set(result.completed) == {"C1", "C2", "C3", "C4"}
    assert result.n_vehicles_that_served >= 2
    assert result.n_charge_starts >= 1
    assert result.n_decisions >= 2
    kinds = {r.kind for r in log}
    assert "charge_start" in kinds
    assert "request_release" in kinds
    art = write_phase_b_artifact(tmp_path)
    assert art["all_criteria_met"] is True


def test_phase_b_observation_has_no_hidden_future_field():
    assert "hidden" not in Observation.__dataclass_fields__


def test_adversarial_replay_rejects_impossible_charge_and_interrupted_travel():
    instance = make_reference_instance("easy")
    result = run_episode(
        instance,
        [("C1", 0.0), ("C2", 0.0), ("C3", 30.0)],
        fleet_size=2,
        horizon=200,
        max_replan_interval=40,
        t_max=200,
    )
    assert validate_log(instance, result.log).ok

    charge = LogRecord(
        time=0.0,
        seq=10_000,
        kind="charge_start",
        vehicle_id="v1",
        data={"station": "C1", "target": 50.0, "soc": 50.0, "duration": 0.0},
    )
    bad_charge = copy.deepcopy(result.log)
    bad_charge.append(charge)
    assert validate_log(instance, bad_charge).ok is False

    interrupted = copy.deepcopy(result.log)
    depart = next(r for r in interrupted if r.kind == "depart")
    arrive_i = next(
        i
        for i, r in enumerate(interrupted)
        if r.kind == "arrive" and r.vehicle_id == depart.vehicle_id and r.seq > depart.seq
    )
    twin = copy.deepcopy(depart)
    twin.seq = max(r.seq for r in interrupted) + 1
    interrupted.insert(arrive_i, twin)
    assert validate_log(instance, interrupted).code == "interrupted_travel"
