"""Legacy Phase-3 toy gate (restricted suffix skeletons) + pointers to Phase 3B plant tests."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.state import Visit
from safe_time_evrp.mpc_central.first_action_eval import choose_policies, gate_report, simulate_prefix
from safe_time_evrp.mpc_central.forks import (
    case_a_predictive_charging_fork,
    case_b_irreversible_admission_fork,
    phase3_forks,
)


def test_case_a_prefixes_feasible():
    spec = case_a_predictive_charging_fork()
    energy = NominalLinearEnergy()
    a = spec.observation.vehicles[0].anchor
    assert simulate_prefix(spec.instance, a, [Visit("Near", "service")], energy).feasible
    assert simulate_prefix(spec.instance, a, [Visit("S", "charge")], energy).feasible


def test_case_b_toy_prediction_changes_admission():
    """Toy enumerator still shows prediction flip on admission (not an exact plant oracle)."""
    choice = choose_policies(case_b_irreversible_admission_fork())
    assert choice.reactive == "accept_now"
    assert choice.stochastic_rollout == "reject_now"
    assert choice.commitment_safe_mpc == choice.stochastic_rollout


def test_legacy_gate_reports_identical_mpc_and_rollout():
    report = gate_report(phase3_forks())
    assert report["n_mpc_differs_from_rollout"] == 0
    out = Path("docs/mpc_central/action_causality_gate.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
