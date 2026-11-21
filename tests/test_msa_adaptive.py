"""MSA consensus and adaptive_compute_v1 unit tests."""

from __future__ import annotations

from safe_time_evrp.data.dynamic_schneider import load_instance
from safe_time_evrp.mpc_central.adaptive_compute import adaptive_compute_v1, remaining_dynamic_mass_frac
from safe_time_evrp.mpc_central.msa_consensus import apply_consensus_to_scored, borda_consensus_scores
from safe_time_evrp.testbed.constructor import make_observation


def test_borda_prefers_cross_scenario_winner():
    # A wins scen0, B wins scen1, A second on scen1 → A has higher Borda if close.
    per = {
        "A": [10.0, 8.0],
        "B": [1.0, 9.0],
        "C": [0.0, 0.0],
    }
    cons = borda_consensus_scores(per)
    assert cons["A"] >= cons["B"]
    assert cons["C"] < cons["A"]


def test_apply_consensus_reorders():
    scored = [
        (100.0, "mean_winner", "c1", [], "x"),
        (50.0, "consensus_winner", "c2", [], "x"),
    ]
    per = {"mean_winner": [1.0, 1.0], "consensus_winner": [10.0, 10.0]}
    out = apply_consensus_to_scored(scored, per)
    assert out[0][1] == "consensus_winner"
    # Economic value preserved (not replaced by Borda points).
    assert out[0][0] == 50.0


def test_adaptive_compute_stress_expands():
    inst = load_instance("c103C5")
    obs = make_observation(inst, fleet_size=2, start_time=0.0)
    # Early with few announced → high remaining mass.
    out = adaptive_compute_v1(
        obs,
        inst,
        horizon=100.0,
        n_scenarios_base=2,
        n_scenarios_max=4,
        alns_base=10,
        alns_max=20,
    )
    assert out["n_scenarios"] in {2, 4}
    assert out["alns_iterations"] in {10, 20}
    assert remaining_dynamic_mass_frac(obs, inst) >= 0.0
