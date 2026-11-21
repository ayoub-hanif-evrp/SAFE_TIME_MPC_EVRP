"""Family-fit forecast loaders and EVRP train/test disjointness."""

from __future__ import annotations

import json
from pathlib import Path

from safe_time_evrp.data.dynamic_schneider import load_instance
from safe_time_evrp.mpc3c.finite_demand_forecast import (
    FiniteDemandTrainEpisode,
    fit_finite_demand_model_from_episodes,
)
from safe_time_evrp.mpc3c.forecast import fit_empirical_arrivals
from safe_time_evrp.mpc_central.family_forecasts import (
    assert_evrp_train_test_disjoint,
    load_family_forecasts,
)

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "docs" / "experiments" / "MPC_EVRP_FAMILY_SPLITS.json"


def test_evrp_train_test_disjoint():
    assert_evrp_train_test_disjoint()
    doc = json.loads(SPLITS.read_text(encoding="utf-8"))
    assert doc["overlap_train_test"] == []
    for scale in ("Cus_5", "Cus_15"):
        assert not (set(doc["train_freeze"][scale]) & set(doc["test_freeze"][scale]))


def test_fit_from_episodes_smoke():
    inst = load_instance("c103C5")
    cust = list(inst.customer_ids())
    known = set(cust[:2])
    dyn = set(cust[2:])
    releases = [(c, 0.0 if c in known else 10.0) for c in cust]
    arrival = fit_empirical_arrivals([inst])
    ep = FiniteDemandTrainEpisode(
        n_customers=len(cust),
        horizon=100.0,
        releases=releases,
        dynamic_arrivals=dyn,
        known_at_start=known,
        instance=inst,
    )
    model = fit_finite_demand_model_from_episodes(
        [ep], train_atoms=arrival.train_atoms, model_id="unit_test"
    )
    assert model.model_id == "unit_test"
    assert model.pooled.n_episodes == 1


def test_load_schneider_family():
    pack = load_family_forecasts("schneider")
    assert pack.family == "schneider"
    assert pack.arrival.train_atoms
    assert "schneider" in pack.finite.model_id


def test_load_evrp_family():
    pack = load_family_forecasts("evrp_tw_d")
    assert pack.family == "evrp_tw_d"
    assert pack.train_meta["n_train_cells"] > 0
    assert "evrp_tw_d" in pack.finite.model_id
