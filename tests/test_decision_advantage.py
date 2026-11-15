"""Stage 3 foundation: paired advantage API smoke."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc
from safe_time_evrp.mpc_central.counterfactual_actions import generate_counterfactual_actions
from safe_time_evrp.mpc_central.decision_advantage import (
    feature_advantage_score,
    paired_causal_advantage,
    screen_by_features,
)


def test_paired_advantage_smoke():
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    ctrl = CertificateCarryingEconomicMpc(
        case.instance,
        case.horizon,
        use_forecast=False,
        scoring_mode="greedy_nominal",
        alns_iterations=4,
        time_limit_seconds=0.4,
        seed=1,
        rollout_max_events=40,
    )
    incumb = ctrl.decide(obs, "initial")
    cands, _ = generate_counterfactual_actions(
        case.instance,
        obs,
        horizon=case.horizon,
        alns_iterations=4,
        alns_time=0.1,
        seed=1,
        include_solver_baselines=True,
        include_b1=True,
    )
    if not cands:
        return
    name, cand = cands[0]
    est = paired_causal_advantage(
        case.instance,
        obs,
        name,
        cand,
        incumb,
        [[]],
        horizon=case.horizon,
        max_events=40,
    )
    assert est.n_scenarios == 1
    assert isinstance(est.feature_score, float)
    scored = screen_by_features(obs, incumb, cands[:5], expected_remaining=1.0, keep=2)
    assert len(scored) <= 2
    _ = feature_advantage_score(obs, cand, incumb, expected_remaining=1.0)
