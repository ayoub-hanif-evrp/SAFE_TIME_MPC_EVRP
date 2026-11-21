"""Unit tests for M1/M2 accept discipline helpers."""

from __future__ import annotations

from safe_time_evrp.data.dynamic_schneider import load_instance
from safe_time_evrp.models.state import Anchor, Observation, VehicleView
from safe_time_evrp.mpc_central.accept_slack import filter_accepts_by_slack
from safe_time_evrp.mpc_central.commitment_safe_stochastic_mpc import (
    CommitmentSafeStochasticMpc,
    FeasibilityClass,
)


def test_hard_terminal_strips_accepts():
    inst = load_instance("c103C5")
    ctrl = CommitmentSafeStochasticMpc(
        inst,
        horizon=100.0,
        use_forecast=False,
        n_scenarios=1,
        hard_terminal_accepts=True,
        accept_slack_gate=False,
        time_limit_seconds=0.2,
        seed=0,
    )
    bat = float(inst.vehicle_type.battery_capacity)
    anchor = Anchor(inst.depot_id, 0.0, bat, 0.0, frozenset())
    vv = VehicleView("V0", "idle", inst.depot_id, bat, 0.0, (), anchor, None)
    obs = Observation(
        time=0.0,
        vehicles=(vv,),
        released_open=("C1",),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=(),
        deferred=(),
        public_customer_count=5,
    )
    notes: list[str] = []
    newly, rejected = ctrl._discipline_new_accepts(
        obs,
        routes={"V0": []},
        newly=["C1"],
        rejected=[],
        best_cls=FeasibilityClass.SOFT_TERMINAL,
        notes=notes,
    )
    assert newly == []
    assert "C1" in rejected
    assert any(n.startswith("hard_terminal_accepts_stripped=") for n in notes)


def test_filter_accepts_api_empty():
    inst = load_instance("c103C5")
    bat = float(inst.vehicle_type.battery_capacity)
    anchor = Anchor(inst.depot_id, 0.0, bat, 0.0, frozenset())
    vv = VehicleView("V0", "idle", inst.depot_id, bat, 0.0, (), anchor, None)
    obs = Observation(
        time=0.0,
        vehicles=(vv,),
        released_open=(),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=(),
        deferred=(),
    )
    kept, stripped, diag = filter_accepts_by_slack(
        inst, obs, {"V0": []}, [], gamma_time=5.0, gamma_energy=0.05
    )
    assert kept == [] and stripped == [] and diag == []
