"""Gate 3A trustworthiness regressions for seeds, horizon, and information boundary."""

from __future__ import annotations

import inspect

from safe_time_evrp.models.state import Anchor, Observation, VehicleView
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.robust.anytime import improve
from safe_time_evrp.robust.dev_study import stable_seed
from safe_time_evrp.robust.uncertainty import RectangularUncertainty


def test_stable_seed_is_policy_independent_and_deterministic():
    a = stable_seed("c101C5", "mixed")
    b = stable_seed("c101C5", "mixed")
    c = stable_seed("c101C5", "upper")
    assert a == b
    assert a != c
    assert 0 <= a < 10_000


def test_legacy_improve_documents_unused_horizon():
    source = inspect.getsource(improve)
    assert "intentionally unused" in source or "_ = horizon" in source
    instance = make_reference_instance("easy")
    soc = instance.vehicle_type.battery_capacity
    anchor = Anchor(instance.depot_id, 0.0, soc, 0.0, frozenset())
    view = VehicleView("v1", "idle", instance.depot_id, soc, 0.0, (), anchor, None)
    observation = Observation(0.0, (view,), ("C1",), (), (), (), (), ())
    # Different horizons must not change the constructive search on this baseline.
    plans_a = list(
        improve(
            instance,
            observation,
            {"v1": []},
            RectangularUncertainty(),
            steps=3,
            horizon=10.0,
            allowed_customers=frozenset({"C1"}),
        )
    )
    plans_b = list(
        improve(
            instance,
            observation,
            {"v1": []},
            RectangularUncertainty(),
            steps=3,
            horizon=999.0,
            allowed_customers=frozenset({"C1"}),
        )
    )
    assert plans_a[-1]["routes"] == plans_b[-1]["routes"]


def test_allowed_customers_blocks_hidden_ids():
    instance = make_reference_instance("easy")
    soc = instance.vehicle_type.battery_capacity
    anchor = Anchor(instance.depot_id, 0.0, soc, 0.0, frozenset())
    view = VehicleView("v1", "idle", instance.depot_id, soc, 0.0, (), anchor, None)
    # Observation lists C2 as released, but the payload forbids it.
    observation = Observation(0.0, (view,), ("C1", "C2"), (), (), (), (), ())
    plans = list(
        improve(
            instance,
            observation,
            {"v1": []},
            RectangularUncertainty(),
            steps=5,
            horizon=100.0,
            allowed_customers=frozenset({"C1"}),
        )
    )
    served = {
        visit.node_id for visits in plans[-1]["routes"].values() for visit in visits if visit.purpose == "service"
    }
    assert "C2" not in served


def test_part25_intervening_event_regression_still_enforced():
    """Gate 3A keeps Part 2.5 plant-time causality coverage in the suite."""
    from tests.test_part2_5_correctness import test_intervening_event_blocks_stale_dispatch

    test_intervening_event_blocks_stale_dispatch()
