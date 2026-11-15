"""Stage 2: contract tests — anytime+override store sync beyond bare M1 publish."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc_central.baseline_anchored_predictive_cce import BaselineAnchoredPredictiveCCE
from safe_time_evrp.mpc_central.cce_mpc import CertificateCarryingEconomicMpc


def _obs():
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    return case, sim.observation()


def test_shared_store_identity_and_matched_budget():
    case, obs = _obs()
    bap = BaselineAnchoredPredictiveCCE(
        case.instance,
        case.horizon,
        allow_override=False,
        equivalence_mode=True,
        alns_iterations=4,
        time_limit_seconds=0.4,
        seed=0,
        use_finite_demand=False,
        rollout_max_events=40,
    )
    assert bap.store is bap._incumbent.store
    assert bap._incumbent.time_limit_seconds == 1e9
    d = bap.decide(obs, "initial")
    assert "zero_override_passthrough" in d.notes
    # After passthrough, store should be the incumbent's published cert (if any).
    assert bap.store is bap._incumbent.store


def test_emit_never_claims_certified_without_validation_path():
    case, obs = _obs()
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
    d = ctrl.decide(obs, "initial")
    if "CERTIFIED" in str(getattr(ctrl, "last_validation_status", "")):
        assert d.no_feasible_continuation is False


def test_override_resync_hook_exists_and_runs_without_error():
    case, obs = _obs()
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    bap = BaselineAnchoredPredictiveCCE(
        case.instance,
        case.horizon,
        finite_model=finite,
        allow_override=True,
        alns_iterations=4,
        time_limit_seconds=0.5,
        seed=2,
        rollout_max_events=40,
        improvement_margin=1e9,  # force keep-incumbent; sync path still available
    )
    d = bap.decide(obs, "initial")
    assert bap.store is bap._incumbent.store
    assert d is not None
