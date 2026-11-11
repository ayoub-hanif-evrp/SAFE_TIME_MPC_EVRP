"""Phase-3 action-causality gate for MPC-central research."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.state import Visit
from safe_time_evrp.mpc_central.first_action_eval import choose_policies, gate_report, simulate_prefix
from safe_time_evrp.mpc_central.forks import case_a_predictive_charging_fork, case_b_irreversible_admission_fork


def test_case_a_prefixes_feasible():
    spec = case_a_predictive_charging_fork()
    energy = NominalLinearEnergy()
    a = spec.observation.vehicles[0].anchor
    assert simulate_prefix(spec.instance, a, [Visit("Near", "service")], energy).feasible
    assert simulate_prefix(spec.instance, a, [Visit("S", "charge")], energy).feasible


def test_case_a_prediction_changes_first_action():
    choice = choose_policies(case_a_predictive_charging_fork())
    assert choice.reactive == "serve_near"
    assert choice.stochastic_rollout == "charge_first"
    assert choice.commitment_safe_mpc == choice.stochastic_rollout


def test_case_b_prediction_changes_admission():
    choice = choose_policies(case_b_irreversible_admission_fork())
    assert choice.reactive == "accept_now"
    assert choice.stochastic_rollout == "reject_now"
    assert choice.commitment_safe_mpc == choice.stochastic_rollout


def test_gate_report_revise_not_clairvoyant_novelty():
    report = gate_report()
    assert report["n_prediction_diverges_from_reactive"] == 2
    assert report["n_mpc_differs_from_rollout"] == 0
    assert report["verdict"] == "REVISE"
    out = Path("docs/mpc_central/action_causality_gate.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
