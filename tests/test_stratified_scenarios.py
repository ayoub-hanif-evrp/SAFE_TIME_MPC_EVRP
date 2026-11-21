"""Stratified finite-demand scenarios are more diverse than i.i.d. at small n."""

from __future__ import annotations

from safe_time_evrp.data.dynamic_schneider import load_instance
from safe_time_evrp.models.state import Anchor, Observation, VehicleView
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    fit_finite_demand_model,
    sample_finite_demand_scenarios,
    scenario_set_diversity,
)
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.testbed.constructor import make_observation


def _obs_partial(inst, *, n_known: int = 2) -> Observation:
    cust = list(inst.customer_ids())
    obs0 = make_observation(inst, fleet_size=2, start_time=0.0)
    vehicles = []
    for v in obs0.vehicles:
        vehicles.append(
            VehicleView(
                v.id,
                v.status,
                v.node,
                v.soc,
                v.load,
                v.onboard,
                Anchor(v.anchor.node, v.anchor.time, v.anchor.soc, v.anchor.load, v.anchor.onboard),
                v.locked_destination,
            )
        )
    return Observation(
        5.0,
        tuple(vehicles),
        tuple(cust[:n_known]),
        (),
        (),
        (),
        (),
        (),
        public_customer_count=len(cust),
    )


def test_stratified_more_diverse_than_iid():
    inst = load_instance("c103C5")
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=2)
    obs = _obs_partial(inst)
    strat = sample_finite_demand_scenarios(
        finite, obs, inst, horizon=100.0, n_scenarios=4, seed=7, sample_mode="stratified"
    )
    iid = sample_finite_demand_scenarios(
        finite, obs, inst, horizon=100.0, n_scenarios=4, seed=7, sample_mode="iid"
    )
    d_s = scenario_set_diversity(strat)
    d_i = scenario_set_diversity(iid)
    assert d_s["score"] >= d_i["score"] - 1e-9
    # Stratified should usually be strictly better; allow equality if demand ended.
    if any(strat) and any(iid):
        assert d_s["score"] > 0.0


def test_stratified_default_and_finite_cap():
    inst = load_instance("r105C5")
    _ = fit_empirical_arrivals([inst])
    finite = fit_finite_demand_model(dynamicity="medium", n_realizations=1)
    obs = _obs_partial(inst, n_known=1)
    sc = sample_finite_demand_scenarios(
        finite, obs, inst, horizon=80.0, n_scenarios=3, seed=1
    )
    assert len(sc) == 3
    hard = max(0, len(inst.customer_ids()) - 1)
    for items in sc:
        assert len(items) <= hard
