"""Forecast noninterference and calibration checks for the MPC-central track.

Reuses ``mpc3c.forecast`` train-only anonymous sampling. Controllers/planning
copies must not depend on unreleased evaluation customer identities or geometry.
"""

from __future__ import annotations

import pytest

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation
from safe_time_evrp.mpc3c.forecast import (
    ArrivalForecast,
    TrainDemandAtom,
    augment_instance_for_planning,
    build_anonymous_scenarios,
    build_scenarios_for,
    fit_empirical_arrivals,
    visible_forecast,
)
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.testbed.constructor import make_observation


def _train_instances() -> list:
    vehicle = VehicleType(40.0, 10.0, 1.0, 0.2, 1.0, "full")
    out = []
    for i, (x, y) in enumerate(((2.0, 1.0), (3.0, 2.0), (1.5, 2.5))):
        nodes = [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
            Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
            Node(f"T{i}", NodeKind.CUSTOMER, x, y, 1, TimeWindow(0, 80 + 10 * i), 1),
        ]
        out.append(
            build_euclidean_instance(
                f"train_{i}",
                nodes,
                vehicle,
                source_format="synthetic",
                source_name="mpc_central_train",
                assumptions=("train_split_only",),
            )
        )
    return out


def test_fit_on_train_only_and_anonymous_ids():
    model = fit_empirical_arrivals(_train_instances())
    assert model.train_atoms
    assert "NOT_valid_announcement_interarrival" in model.model_id
    fcst = build_anonymous_scenarios(model, n_scenarios=2, customers_per_scenario=2, seed=stable_seed("mc", "f"))
    ids = [c.customer_id for sc in fcst.scenarios for c in sc]
    assert ids
    assert all(cid.startswith("syn_") for cid in ids)
    assert not any(cid.startswith("T") for cid in ids)


def test_build_scenarios_for_rejects_eval_instance():
    train = fit_empirical_arrivals(_train_instances())
    eval_inst = _train_instances()[0]
    with pytest.raises(RuntimeError, match="quarantined"):
        build_scenarios_for(eval_inst, train)


def test_visible_forecast_excludes_known_and_is_horizon_limited():
    model = ArrivalForecast(
        train_atoms=(TrainDemandAtom(2, 2, 1, 1, 0, 40),),
        train_interarrival_mean=3.0,
        model_id="unit",
    )
    fcst = build_anonymous_scenarios(model, n_scenarios=1, customers_per_scenario=3, seed=1, day_horizon=100.0)
    inst = _train_instances()[0]
    obs = make_observation(inst, 1)
    # Pretend one synthetic id is already known — must be excluded.
    known = fcst.scenarios[0][0].customer_id
    obs = Observation(0.0, obs.vehicles, (known,), (), (), (), (), ())
    visible = visible_forecast(obs, fcst, horizon=10.0, scenario_index=0)
    assert all(c.customer_id != known for c in visible)
    assert all(c.ready_time <= 10.0 + 1e-9 for c in visible)


def test_augment_instance_keeps_syn_out_of_eval_dispatch_contract():
    """Planning clone may contain syn_* nodes; eval observation customers must not."""
    model = fit_empirical_arrivals(_train_instances())
    fcst = build_anonymous_scenarios(model, n_scenarios=1, customers_per_scenario=2, seed=2)
    eval_inst = _train_instances()[0]
    forecasts = fcst.scenarios[0]
    planning = augment_instance_for_planning(eval_inst, forecasts)
    assert any(n.id.startswith("syn_") for n in planning.customers)
    assert not any(n.id.startswith("syn_") for n in eval_inst.customers)


def test_forecast_noninterference_under_hidden_eval_mutations():
    """Anonymous forecasts + public released set must not change with hidden eval geometry."""
    model = ArrivalForecast(
        train_atoms=(
            TrainDemandAtom(2.0, 2.0, 1.0, 1.0, 1.0, 40.0),
            TrainDemandAtom(3.0, 1.0, 1.0, 1.0, 2.0, 50.0),
        ),
        train_interarrival_mean=3.0,
        model_id="unit",
    )
    fcst = build_anonymous_scenarios(model, n_scenarios=2, customers_per_scenario=2, seed=stable_seed("mc", "n"))
    forecasts = fcst.sample_within(0.0, 30.0)

    def env(hidden):
        nodes = [
            Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
            Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
            Node("A", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 80), 1),
            *hidden,
        ]
        vehicle = VehicleType(40.0, 10.0, 1.0, 0.2, 1.0, "full")
        return build_euclidean_instance("n", nodes, vehicle, source_format="t", source_name="t", assumptions=())

    ea = env([Node("H1", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(50, 120), 1)])
    eb = env(
        [
            Node("HX", NodeKind.CUSTOMER, 0, 30, 1, TimeWindow(60, 90), 1),
            Node("HY", NodeKind.CUSTOMER, 25, 25, 1, TimeWindow(70, 150), 1),
        ]
    )
    oa = Observation(0.0, make_observation(ea, 1).vehicles, ("A",), (), (), (), (), ())
    ob = Observation(0.0, make_observation(eb, 1).vehicles, ("A",), (), (), (), (), ())
    va = visible_forecast(oa, fcst, 20.0)
    vb = visible_forecast(ob, fcst, 20.0)
    assert [c.customer_id for c in va] == [c.customer_id for c in vb]
    assert [c.customer_id for c in forecasts]  # calibrated sample nonempty
    pa = augment_instance_for_planning(ea, va)
    pb = augment_instance_for_planning(eb, vb)
    syn_a = sorted(n.id for n in pa.customers if n.id.startswith("syn_"))
    syn_b = sorted(n.id for n in pb.customers if n.id.startswith("syn_"))
    assert syn_a == syn_b
