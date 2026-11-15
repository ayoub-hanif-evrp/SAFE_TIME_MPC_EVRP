"""DecisionFocusedBAP smoke."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_baseline_suite
from safe_time_evrp.environment.simulator import FleetSimulator
from safe_time_evrp.mpc3c.finite_demand_forecast import fit_finite_demand_model
from safe_time_evrp.mpc_central.decision_focused_bap import DecisionFocusedBAP


def test_decision_focused_bap_decide():
    case = next(c for c in build_baseline_suite() if c.case_id == "B_easy_dynamic")
    sim = FleetSimulator(case.instance, case.fleet_size)
    for cid, t in case.releases:
        sim.schedule_release(cid, t)
    while sim.next_event_time() is not None and sim.next_event_time() <= 1e-12:
        sim.pop_event()
    obs = sim.observation()
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    ctrl = DecisionFocusedBAP(
        case.instance,
        case.horizon,
        finite_model=finite,
        alns_iterations=4,
        time_limit_seconds=0.5,
        seed=0,
        rollout_max_events=40,
        tau=0.5,
    )
    d = ctrl.decide(obs, "initial")
    assert "decision_focused_bap" in d.notes
    assert ctrl.profile.decisions == 1
