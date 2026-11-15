"""Regression: colocated depot/charger must not stall the decision loop."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.data.dynamic_schneider import build_dynamic_episode, load_instance, stratified_split_small
from safe_time_evrp.data.paths import schneider_dir
from safe_time_evrp.mpc3c.forecast import build_anonymous_scenarios, fit_empirical_arrivals
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc


def _have_results_and_data() -> bool:
    return (schneider_dir() / "extracted").is_dir() and Path(
        "docs/experiments/SCHNEIDER_DYNAMIC_RESULTS.json"
    ).is_file()


@pytest.mark.skipif(not _have_results_and_data(), reason="needs Schneider data + v1 results artifact")
def test_previous_cce_stall_case_completes_without_decision_loop_error():
    payload = json.loads(Path("docs/experiments/SCHNEIDER_DYNAMIC_RESULTS.json").read_text(encoding="utf-8"))
    row = next(
        r
        for r in payload["rows"]
        if r["controllers"]["cce_mpc"].get("failure")
        and "decision loop did not advance time" in r["controllers"]["cce_mpc"]["failure"]
    )
    ep = build_dynamic_episode(
        row["instance_stem"],
        environment_seed=row["environment_seed"],
        policy_seed=row["policy_seed"],
        dynamicity=row["dynamicity"],
    )
    case = ep.case
    splits = stratified_split_small()
    forecast = build_anonymous_scenarios(
        fit_empirical_arrivals([load_instance(s) for s in splits["train"]]),
        n_scenarios=2,
        customers_per_scenario=2,
        seed=stable_seed("schneider_dyn_train_forecast", "0", "2026-11-14.v1"),
        announcement_mean=12.0,
    )
    ctrl = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        forecast=forecast,
        n_scenarios=2,
        alns_iterations=10,
        time_limit_seconds=0.35,
        seed=row["policy_seed"],
        use_forecast=True,
        use_persistent_certificate=True,
        max_replan_interval=case.max_replan_interval,
        rollout_max_events=200,
    )
    result = run_episode(
        case.instance,
        case.releases,
        fleet_size=case.fleet_size,
        horizon=case.horizon,
        max_replan_interval=case.max_replan_interval,
        t_max=case.t_max,
        controller=ctrl,
    )
    assert result.termination_reason in {
        "natural_completion",
        "cutoff_next_event_after_tmax",
        "no_pending_events",
    }
    assert len(result.decisions) > 0
