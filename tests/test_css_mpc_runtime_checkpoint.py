"""Phase-4 remaining: checkpointed scoring + commit-time reserve."""

from __future__ import annotations

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import CommitmentSafeStochasticMpc
from safe_time_evrp.testbed.constructor import make_observation


def _toy():
    vehicle = VehicleType(80.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 4, 0, 1, TimeWindow(0, 100), 5),
        Node("C2", NodeKind.CUSTOMER, 6, 1, 1, TimeWindow(20, 120), 5),
    ]
    return build_euclidean_instance(
        "runtime_toy",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="runtime",
        assumptions=("runtime",),
    )


def test_checkpointed_scoring_notes_and_reserve():
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1", "C2"), (), (), (), (), (), public_customer_count=2)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        alns_iterations=4,
        time_limit_seconds=0.35,
        seed=1,
        commit_reserve_fraction=0.2,
        max_scenario_expansions=2,
    )
    d = ctrl.decide(obs, "request_release")
    assert "checkpointed_scoring=1" in d.notes
    assert any(n.startswith("commit_reserve_s=") for n in d.notes)
    assert any(n.startswith("n_unique_first_actions=") for n in d.notes)
    assert any(n.startswith("n_empty_checkpoint=") for n in d.notes)
    assert "no_forecast_expand_skipped" in d.notes
    assert d.optimize_seconds < 0.35 or "deadline_overrun" in d.notes


def test_tiny_budget_still_emits_decision():
    """Under a tiny cooperative budget, decide must still return a Decision (fallback OK)."""
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=1)
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=80.0,
        use_forecast=False,
        alns_iterations=8,
        time_limit_seconds=0.05,
        seed=3,
        commit_reserve_fraction=0.25,
    )
    d = ctrl.decide(obs, "request_release")
    assert d is not None
    assert isinstance(d.newly_accepted, list)
    assert "checkpointed_scoring=1" in d.notes
