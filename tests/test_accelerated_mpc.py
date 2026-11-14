"""Accelerated MPC mission: cloning, terminal value, counterfactuals, pilot smoke."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Decision, Visit
from safe_time_evrp.mpc3c.forecast import ArrivalForecast, ForecastCustomer, TrainDemandAtom, build_anonymous_scenarios
from safe_time_evrp.mpc_central.accelerated_pilot import (
    action_diversity_gate,
    build_accelerated_dev_matrix,
    run_accelerated_pilot,
)
from safe_time_evrp.mpc_central.counterfactual_actions import FirstActionKey
from safe_time_evrp.mpc_central.forks import case_a_predictive_charging_fork
from safe_time_evrp.mpc_central.scenario_rollout import (
    announcement_release_time,
    is_quiescent,
    rollout_candidate,
    seed_simulator_from_observation,
)


def _advance_to_mid_travel(spec):
    sim = FleetSimulator(spec.instance, 1)
    for cid, t in spec.base_releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    vid = next(iter(sim.vehicles))
    sim.apply_decision(
        Decision(
            0.0,
            {vid: [Visit("Near", "service")]},
            ["Near"],
            ["Near"],
            [],
            [],
            False,
            False,
            False,
            ["Near"],
            0.0,
            0.0,
            0.0,
            "t",
            {},
            [],
        )
    )
    # Pop until traveling
    for _ in range(5):
        obs = sim.observation()
        if obs.vehicles[0].status == "traveling":
            return sim, obs
        ev = sim.pop_event()
        if ev is None:
            break
    return sim, sim.observation()


def test_busy_vehicle_clone_keeps_clock_and_current_node():
    spec = case_a_predictive_charging_fork()
    sim, obs = _advance_to_mid_travel(spec)
    assert obs.vehicles[0].status == "traveling"
    assert not is_quiescent(obs)
    fork = seed_simulator_from_observation(spec.instance, obs)
    assert abs(fork.time - obs.time) <= 1e-12
    v = next(iter(fork.vehicles.values()))
    assert v.node == obs.vehicles[0].node  # not teleported to anchor
    assert v.status.value == "traveling"
    assert v.anchor_after is not None
    assert abs(v.anchor_after.time - obs.vehicles[0].anchor.time) <= 1e-9
    # Completing the restored arrive should match plant destination
    plant_dest = obs.vehicles[0].locked_destination
    while fork.next_event_time() is not None:
        ev = fork.pop_event()
        if ev and ev.kind == "arrive":
            assert fork.vehicles[v.id].node == plant_dest
            break


def test_mid_travel_clone_matches_plant_arrival_soc():
    spec = case_a_predictive_charging_fork()
    sim, obs = _advance_to_mid_travel(spec)
    fork = seed_simulator_from_observation(spec.instance, obs)
    # Advance both to arrival
    while sim.next_event_time() is not None:
        ev = sim.pop_event()
        if ev and ev.kind == "arrive":
            break
    while fork.next_event_time() is not None:
        ev = fork.pop_event()
        if ev and ev.kind == "arrive":
            break
    pv = next(iter(sim.vehicles.values()))
    fv = next(iter(fork.vehicles.values()))
    assert abs(pv.soc - fv.soc) <= 1e-6
    assert pv.node == fv.node


def test_horizon_terminal_does_not_force_au_when_residual_feasible():
    spec = case_a_predictive_charging_fork()
    sim = FleetSimulator(spec.instance, 1)
    for cid, t in spec.base_releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    vid = obs.vehicles[0].id
    cand = Decision(
        time=0.0,
        routes={vid: [Visit("Near", "service")]},
        accepted=["Near"],
        newly_accepted=["Near"],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=["Near"],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="t",
        locked_destinations={},
        notes=[],
    )
    # Very short horizon — may not finish service
    short = rollout_candidate(spec.instance, obs, cand, [], horizon=0.01, max_events=50)
    assert "horizon_end_residual_" in "".join(short.notes)
    # Extending horizon should not invent AU if residual was feasible
    long = rollout_candidate(spec.instance, obs, cand, [], horizon=200.0, max_events=500)
    if "horizon_end_residual_feasible" in short.notes:
        assert short.accepted_unfulfilled == () or "Near" not in short.accepted_unfulfilled or long.completed


def test_announcement_time_separate_from_ready():
    fc = ForecastCustomer("syn", ready_time=20.0, due_time=50.0, x=1, y=1, announcement_time=5.0)
    assert announcement_release_time(fc, 0.0) == 5.0
    model = ArrivalForecast(train_atoms=(TrainDemandAtom(1, 1, 1, 1, 0, 40),), model_id="t")
    fcst = build_anonymous_scenarios(model, n_scenarios=1, customers_per_scenario=2, seed=1, announcement_mean=8.0)
    assert all(item.announcement_time is not None for item in fcst.scenarios[0])
    assert "preregistered_announcement_mu" in fcst.model_id


def test_counterfactual_actions_produce_distinct_safe_keys():
    cases = build_accelerated_dev_matrix()
    gate = action_diversity_gate(cases[0])
    assert gate["valid_commitment_safe"] >= 2
    assert gate["pass"]


def test_first_action_key_canonicalizes():
    d1 = Decision(
        0, {"v1": [Visit("A", "service")]}, ["A"], ["A"], [], [], False, False, False, ["A"], 0, 0, 0, "t", {}, []
    )
    d2 = Decision(
        0,
        {"v1": [Visit("A", "service"), Visit("B", "service")]},
        ["A"],
        ["A"],
        [],
        [],
        False,
        False,
        False,
        ["A"],
        0,
        0,
        0,
        "t",
        {},
        ["x"],
    )
    assert FirstActionKey.from_decision(d1) == FirstActionKey.from_decision(d2)


def test_accelerated_pilot_smoke_writes_tmp_only(tmp_path):
    out = tmp_path / "accelerated_smoke.json"
    before = None
    tracked = Path("docs/mpc_central/accelerated_results.json")
    if tracked.exists():
        before = tracked.read_text(encoding="utf-8")
    art = run_accelerated_pilot(
        max_cases=2, alns_iterations=6, alns_time=0.25, seed=3, out_path=out, write_tracked_default=False
    )
    assert art["verdict"] in {"GO", "REVISE", "NO-GO"}
    assert art["holdout_untouched"]
    assert all(d["valid_commitment_safe"] >= 1 for d in art["diversity_gate"])
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["summary"]["n_cases"] == 2
    # Unit tests must not overwrite the tracked research artifact.
    if before is not None:
        assert tracked.read_text(encoding="utf-8") == before
