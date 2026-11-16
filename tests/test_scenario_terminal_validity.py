"""Scenario-terminal validity: cache keys and selection must not claim unchecked OK."""

from __future__ import annotations

from unittest.mock import patch

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc3c.forecast import ForecastCustomer
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import (
    CommitmentSafeStochasticMpc,
    FeasibilityClass,
    scenario_set_signature,
)
from safe_time_evrp.mpc_central.terminal_commitment import TerminalCommitmentReport, TerminalRejectReason
from safe_time_evrp.testbed.constructor import make_observation


def _toy():
    vehicle = VehicleType(80.0, 20.0, 1.0, 0.2, 1.0, "full")
    nodes = [
        Node("D0", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S0", NodeKind.CHARGER, 2, 0, 0, TimeWindow(0, 200), 0),
        Node("C1", NodeKind.CUSTOMER, 4, 0, 1, TimeWindow(0, 100), 5),
        Node("C2", NodeKind.CUSTOMER, 8, 0, 1, TimeWindow(0, 40), 5),
    ]
    return build_euclidean_instance(
        "scen_term_toy",
        nodes,
        vehicle,
        source_format="synthetic",
        source_name="scen_term",
        assumptions=("scen_term",),
    )


def test_scenario_set_signature_distinguishes_empty_and_nonempty():
    empty = scenario_set_signature([[]])
    nonempty = scenario_set_signature(
        [
            [
                ForecastCustomer(
                    customer_id="C2",
                    ready_time=0.0,
                    due_time=40.0,
                    x=8.0,
                    y=0.0,
                    demand=1.0,
                    service_time=5.0,
                    announcement_time=5.0,
                )
            ]
        ]
    )
    assert empty != nonempty


def test_terminal_cache_does_not_reuse_empty_for_stochastic():
    """Empty-future OK must not satisfy a nonempty scenario-set cache lookup."""
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=1)
    ctrl = CommitmentSafeStochasticMpc(inst, 40.0, use_forecast=True, time_limit_seconds=1.0, seed=1)
    cache: dict = {}
    # Build a trivial idle decision.
    from safe_time_evrp.models.state import Decision

    cand = Decision(
        time=0.0,
        routes={v.id: [] for v in obs.vehicles},
        accepted=list(obs.accepted),
        newly_accepted=[],
        rejected=[],
        deferred=[],
        fallback_used=False,
        no_feasible_continuation=False,
        horizon_extended=False,
        planned_service=[],
        total_distance=0.0,
        total_charge_time=0.0,
        optimize_seconds=0.0,
        trigger="t",
        locked_destinations={},
        notes=[],
    )
    calls = {"n": 0}

    def fake_project(*args, **kwargs):
        calls["n"] += 1
        fcs = args[3] if len(args) > 3 else kwargs.get("forecasts", [])
        ok = len(fcs) == 0
        return (
            TerminalCommitmentReport(
                ok=ok,
                reason=TerminalRejectReason.OK if ok else TerminalRejectReason.TERMINAL_INFEASIBLE,
                detail="mock",
                seconds=0.0,
            ),
            cand.routes,
        )

    with patch(
        "safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc.project_to_horizon",
        side_effect=fake_project,
    ):
        ok_empty, _ = ctrl._terminal_filter(obs, cand, [[]], deadline=1e18, cache=cache)
        assert ok_empty is True
        n_after_empty = calls["n"]
        future = [
            [
                ForecastCustomer(
                    customer_id="C2",
                    ready_time=0.0,
                    due_time=40.0,
                    x=8.0,
                    y=0.0,
                    demand=1.0,
                    service_time=5.0,
                    announcement_time=5.0,
                )
            ]
        ]
        ok_stoch, detail = ctrl._terminal_filter(obs, cand, future, deadline=1e18, cache=cache)
        assert ok_stoch is False
        assert "terminal_infeasible" in detail
        assert calls["n"] > n_after_empty  # must re-evaluate, not reuse empty cache


def test_scenario_infeasible_candidate_not_selected_as_stochastic():
    """Empty-future feasible + scenario-infeasible ⇒ not selected as scenario-feasible."""
    inst = _toy()
    obs = make_observation(inst, 1)
    obs = Observation(0.0, obs.vehicles, ("C1",), (), (), (), (), (), public_customer_count=2)
    future_fc = ForecastCustomer(
        customer_id="C2",
        ready_time=0.0,
        due_time=40.0,
        x=8.0,
        y=0.0,
        demand=1.0,
        service_time=5.0,
        announcement_time=1.0,
    )
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=30.0,
        use_forecast=True,
        n_scenarios=1,
        alns_iterations=2,
        time_limit_seconds=2.0,
        seed=7,
        require_terminal_commitment=True,
        forecast_override_margin=None,
        scenario_override=[[future_fc]],
        max_scenario_expansions=8,
        commit_reserve_fraction=0.05,
    )

    def fake_project(full, observation, candidate, forecasts, **kwargs):
        # Empty future always OK; nonempty scenario always terminal-infeasible.
        if not forecasts:
            return (
                TerminalCommitmentReport(ok=True, reason=TerminalRejectReason.OK, detail="empty_ok", seconds=0.0),
                candidate.routes,
            )
        return (
            TerminalCommitmentReport(
                ok=False,
                reason=TerminalRejectReason.TERMINAL_INFEASIBLE,
                detail="scenario_block",
                seconds=0.0,
            ),
            candidate.routes,
        )

    with patch(
        "safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc.project_to_horizon",
        side_effect=fake_project,
    ):
        d = ctrl.decide(obs, "request_release")

    # Must not claim stochastic terminal success when every expansion fails.
    assert f"feasibility_class={FeasibilityClass.STOCHASTIC_TERMINAL.value}" not in d.notes
    assert "n_stochastic_terminal=0" in d.notes or "selection_mode=none" in d.notes or d.fallback_used
    # If something was selected via commit, it must not be labeled stochastic_terminal.
    for n in d.notes:
        if n.startswith("feasibility_class="):
            assert n != f"feasibility_class={FeasibilityClass.STOCHASTIC_TERMINAL.value}"
