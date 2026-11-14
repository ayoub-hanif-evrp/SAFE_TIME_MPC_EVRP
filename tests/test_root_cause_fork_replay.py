"""Root-cause gate: snapshot fork replay contract and fail-closed scoring."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.models.state import Decision, Visit
from safe_time_evrp.mpc_central.root_cause_trace import run_root_cause_trace
from safe_time_evrp.mpc_central.scenario_rollout import (
    fork_log_for_replay,
    rollout_candidate,
    seed_simulator_from_observation,
)
from safe_time_evrp.validation.replay import validate_log


def _obs(case_id: str):
    case = {c.case_id: c for c in build_baseline_suite()}[case_id]
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        if t <= 0:
            sim.schedule_release(cid, 0.0)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    return case, sim.observation()


def test_accept_already_announced_customer_passes_fork_replay():
    case, obs = _obs("B_phase_b")
    fork = seed_simulator_from_observation(case.instance, obs)
    assert any(r.kind == "request_release" for r in fork.log)
    vid = obs.vehicles[0].id
    cust = obs.released_open[0]
    fork.apply_decision(
        Decision(
            obs.time,
            {vid: [Visit(cust, "service")]},
            [cust],
            [cust],
            [],
            [],
            False,
            False,
            False,
            [cust],
            0.0,
            0.0,
            0.0,
            "t",
            {},
            [],
        )
    )
    report = validate_log(case.instance, fork_log_for_replay(fork))
    assert report.ok, report.detail


def test_accept_unreleased_customer_still_fails_replay():
    case, obs = _obs("B_phase_b")
    hidden = next(c for c in case.instance.customer_ids() if c not in obs.released_open)
    fork = seed_simulator_from_observation(case.instance, obs)
    fork.apply_decision(
        Decision(
            obs.time,
            {obs.vehicles[0].id: []},
            [hidden],
            [hidden],
            [],
            [],
            False,
            False,
            False,
            [],
            0,
            0,
            0,
            "t",
            {},
            [],
        )
    )
    report = validate_log(case.instance, fork_log_for_replay(fork))
    assert not report.ok
    assert report.code == "early_request_access"


def test_expected_rollout_fail_closed_on_invalid_scenario(monkeypatch):
    case, obs = _obs("B_phase_b")
    vid = obs.vehicles[0].id
    cand = Decision(
        obs.time,
        {vid: [Visit(obs.released_open[0], "service")]},
        [obs.released_open[0]],
        [obs.released_open[0]],
        [],
        [],
        False,
        False,
        False,
        [obs.released_open[0]],
        0,
        0,
        0,
        "t",
        {},
        [],
    )

    real = rollout_candidate

    def boom(*args, **kwargs):
        score = real(*args, **kwargs)
        # Force one invalid scenario
        from dataclasses import replace

        return replace(score, replay_ok=False, replay_code="forced_invalid", value=50.0)

    # Two scenarios: first invalid, second would be valid — mean must be -1e9 fail-closed.
    from safe_time_evrp.mpc_central import scenario_rollout as sr

    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        score = real(*args, **kwargs)
        if calls["n"] == 1:
            from dataclasses import replace

            return replace(score, replay_ok=False, replay_code="forced_invalid", value=999.0)
        return score

    monkeypatch.setattr(sr, "rollout_candidate", flaky)
    mean_v, scores = sr.expected_rollout_value(case.instance, obs, cand, [[], []], horizon=case.horizon, max_events=50)
    assert mean_v <= -1e8
    assert any(not s.replay_ok for s in scores)


def test_root_cause_trace_artifact(tmp_path):
    out = tmp_path / "root_cause_trace.json"
    art = run_root_cause_trace(out_path=out)
    assert out.exists()
    assert art["overall_verdict"] in {
        "IMPLEMENTATION_DEFECT_CONFIRMED",
        "OBJECTIVE_MISSPECIFICATION",
        "GENUINE_POLICY_FAILURE",
    }
    # After repair, early_request_access must not dominate serve candidates on these cases.
    for tr in art["traces"]:
        for cand in tr["candidates"]:
            if cand["first_action_key"]["newly_accepted"]:
                assert not any(sc["replay_code"] == "early_request_access" for sc in cand["scenarios"])
