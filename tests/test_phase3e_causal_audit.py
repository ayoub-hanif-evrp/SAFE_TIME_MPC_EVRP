"""Phase 3E: fairness contract, reject sanitize, and audit smoke."""

from __future__ import annotations

from pathlib import Path

from safe_time_evrp.commitment_safe_mpc.baseline_compare import executed_distance_from_log
from safe_time_evrp.commitment_safe_mpc.predictive_mpc import CommitmentSafePredictiveMpc
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc_central.accelerated_pilot import build_accelerated_dev_matrix
from safe_time_evrp.mpc_central.counterfactual_actions import sanitize_rejects
from safe_time_evrp.mpc_central.phase3d_splits import fit_train_forecast
from safe_time_evrp.mpc_central.phase3e_causal_audit import (
    diagnose_replay,
    fairness_contract_report,
    run_phase3e,
)
from safe_time_evrp.validation.replay import validate_log


def test_sanitize_rejects_drops_completed_and_in_service():
    obs = Observation(
        time=1.0,
        vehicles=(),
        released_open=("C1",),
        accepted=("C2",),
        completed=("C3",),
        rejected=(),
        in_service=("C4",),
        deferred=(),
    )
    assert sanitize_rejects(obs, ["C1", "C3", "C4", "C2"]) == ["C1", "C2"]


def test_fairness_contract_states_equivalence():
    report = fairness_contract_report()
    assert report["finding"] == "EQUIVALENT_TO_STOCHASTIC_ROLLOUT"
    assert report["required_contract"]["same_seed"] is True
    assert "none" in report["algorithmic_difference_if_seeds_matched"].lower()


def test_b_easy_dynamic_predictive_replay_ok():
    diag = diagnose_replay("B_easy_dynamic", seed=7, alns_iterations=6, alns_time=0.2)
    assert diag["replay_ok"] is True
    assert diag["code"] == "ok"


def test_matched_seed_proposed_equals_stochastic_on_easy():
    cases = {c.case_id: c for c in build_accelerated_dev_matrix()}
    case = cases["B_easy_dynamic"]
    forecast = fit_train_forecast()
    seed = 7
    kwargs = dict(
        forecast=forecast,
        n_scenarios=2,
        alns_iterations=6,
        time_limit_seconds=0.2,
        seed=seed,
        allocation="uniform",
        use_counterfactuals=True,
        use_forecast=True,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=120,
    )
    stoch = CommitmentSafePredictiveMpc(case.instance, case.horizon, **kwargs)
    prop = CommitmentSafePredictiveMpc(case.instance, case.horizon, **kwargs)
    ep_kwargs = dict(
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
    )
    r_s = run_episode(case.instance, case.releases, controller=stoch, **ep_kwargs)
    r_p = run_episode(case.instance, case.releases, controller=prop, **ep_kwargs)
    assert r_s.final_requests == r_p.final_requests
    assert abs(executed_distance_from_log(case.instance, r_s.log) - executed_distance_from_log(case.instance, r_p.log)) < 1e-9
    rep_s = validate_log(case.instance, r_s.log)
    rep_p = validate_log(case.instance, r_p.log)
    assert rep_s.ok and rep_s.code == "ok"
    assert rep_p.ok and rep_p.code == "ok"


def test_run_phase3e_writes_artifacts(tmp_path: Path):
    art = run_phase3e(out_dir=tmp_path)
    assert (tmp_path / "phase3e_decision_traces.json").is_file()
    assert (tmp_path / "phase3e_matched_results.json").is_file()
    assert art["traces"]["decision"] in {
        "GENUINE_MPC_FAILURE",
        "GENUINE_MPC_VALUE",
        "EVALUATION_ARTIFACT",
        "MIXED_OR_EQUIVALENT",
    }
    assert "EQUIVALENT_TO_STOCHASTIC_ROLLOUT" in art["traces"]["findings"]
    assert art["matched"]["stoch_equals_proposed_valid"] == art["matched"]["n_valid_cells"]
