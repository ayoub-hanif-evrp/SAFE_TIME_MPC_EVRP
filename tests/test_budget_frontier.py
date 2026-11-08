"""Smoke tests for Priority-7 frontier suite and runner."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.baseline_suite import build_frontier_suite, build_scaled_suite
from safe_time_evrp.commitment_safe_mpc.budget_frontier import run_frontier_study, run_one


def test_frontier_suite_sizes():
    cases = build_frontier_suite()
    sizes = sorted(len(c.instance.customers) for c in cases if "frontier" in c.case_id)
    assert sizes == [10, 20, 30, 50]
    assert any(c.case_id == "B_rescue_pack" for c in cases)
    # Scaled suite still intact after frontier addition.
    scaled = build_scaled_suite()
    assert {c.case_id for c in scaled} >= {"B_scaled_12", "B_scaled_20", "B_scaled_28", "B_rescue_pack"}


def test_frontier_one_run_replays():
    case = next(c for c in build_frontier_suite() if c.case_id == "B_frontier_10")
    row = run_one(case, "m1", budget=0.05, seed=7, iterations=15)
    assert row["replay_ok"]
    assert row["n_customers"] == 10
    assert row["budget_seconds"] == 0.05


def test_frontier_study_quick_subset():
    art = run_frontier_study(
        budgets=(0.05,),
        seeds=(7,),
        iterations=12,
        controllers=("insertion", "b1", "m1"),
        max_customers=10,
    )
    assert art["headline"]["n_raw_runs"] >= 3
    assert art["headline"]["m1_vs_b1_cells"] >= 1
    assert all(r["replay_ok"] for r in art["rows"])
