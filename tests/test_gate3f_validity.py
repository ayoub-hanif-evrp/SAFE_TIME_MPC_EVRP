"""Gate 3F experimental-validity regressions."""

from __future__ import annotations

import math
from statistics import mean

from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Observation, Visit
from safe_time_evrp.mpc3c.controllers import ControllerKind, decide
from safe_time_evrp.mpc3c.forecast import (
    ArrivalForecast,
    TrainDemandAtom,
    build_anonymous_scenarios,
    build_scenarios_for,
    synthetic_poisson_releases,
)
from safe_time_evrp.mpc3c.seeds import stable_seed
from safe_time_evrp.mpc3c.sim_experiment import (
    _routes_cover_commitments,
    robust_routes_cover_commitments,
    run_sim_dynamic,
)
from safe_time_evrp.mpc3c.upper_bound import offline_service_upper_bound
from safe_time_evrp.testbed.constructor import make_observation


def _toy():
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 200), 0),
        Node("S", NodeKind.CHARGER, 1, 0, 0, TimeWindow(0, 200), 0),
        Node("A", NodeKind.CUSTOMER, 3, 0, 1, TimeWindow(0, 80), 1),
        Node("B", NodeKind.CUSTOMER, 0, 4, 1, TimeWindow(10, 100), 1),
        Node("C", NodeKind.CUSTOMER, 5, 5, 1, TimeWindow(20, 120), 1),
    ]
    vehicle = VehicleType(40.0, 10.0, 1.0, 0.2, 1.0, "full")
    return build_euclidean_instance("g3f", nodes, vehicle, source_format="t", source_name="t", assumptions=())


def test_poisson_interarrivals_are_exponential_not_uniform_affine():
    inst = _toy()
    gaps = []
    for seed in range(20):
        releases = synthetic_poisson_releases(inst, seed=seed, mean_interarrival=5.0)
        times = [t for _, t in sorted(releases, key=lambda x: x[1])]
        gaps.extend([times[i + 1] - times[i] for i in range(len(times) - 1)])
    assert gaps
    # Affine-uniform generator had hard upper bound ~1.95*mu; exponential can exceed.
    assert max(gaps) > 1.95 * 5.0
    # Mean of Exp(mu) is mu.
    assert abs(mean(gaps) - 5.0) < 2.5


def test_announcement_not_clamped_to_due():
    inst = _toy()
    releases = synthetic_poisson_releases(inst, seed=0, mean_interarrival=50.0)
    # With large mu, some announcements can exceed dues — that is allowed.
    for cid, t in releases:
        due = float(inst.node(cid).window.due)
        # Must not equal forced clamp min(max(t,ready),due) identity for all.
        ready = float(inst.node(cid).window.ready)
        clamped = min(max(t, ready), due)
        # At least verify we did not systematically force t into [ready, due] via min/max.
        # (Individual equality can happen by chance.)
        _ = clamped
    assert any(t > float(inst.node(cid).window.due) for cid, t in releases) or any(
        t < float(inst.node(cid).window.ready) for cid, t in releases
    )


def test_offline_upper_bound_at_least_online_served():
    inst = _toy()
    releases = [("A", 0.0), ("B", 5.0), ("C", 8.0)]
    ub = offline_service_upper_bound(inst, releases, fleet_size=1)
    online = run_sim_dynamic(
        inst,
        ControllerKind.RH_OPEN_LOOP,
        fleet_size=1,
        horizon=50.0,
        releases=releases,
        t_max=200.0,
    )
    assert ub.static_constructive_served >= len(online.served)


def test_build_scenarios_for_rejects_eval_instance():
    inst = _toy()
    model = ArrivalForecast(
        train_atoms=(TrainDemandAtom(1, 1, 1, 1, 0, 10),),
        train_interarrival_mean=2.0,
        model_id="t",
    )
    try:
        build_scenarios_for(inst, model)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as exc:
        assert "quarantined" in str(exc).lower()


def test_full_decision_noninterference_under_hidden_mutations():
    model = ArrivalForecast(
        train_atoms=(
            TrainDemandAtom(2.0, 2.0, 1.0, 1.0, 1.0, 40.0),
            TrainDemandAtom(3.0, 1.0, 1.0, 1.0, 2.0, 50.0),
        ),
        train_interarrival_mean=3.0,
        model_id="unit",
    )
    fcst = build_anonymous_scenarios(model, n_scenarios=2, customers_per_scenario=2, seed=stable_seed("f", "n"))
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

    hidden_a = [Node("H1", NodeKind.CUSTOMER, 20, 0, 1, TimeWindow(50, 120), 1)]
    hidden_b = [
        Node("HX", NodeKind.CUSTOMER, 0, 30, 1, TimeWindow(60, 90), 1),
        Node("HY", NodeKind.CUSTOMER, 25, 25, 1, TimeWindow(70, 150), 1),
    ]
    ea, eb = env(hidden_a), env(hidden_b)
    oa = make_observation(ea, 1)
    oa = Observation(oa.time, oa.vehicles, ("A",), (), (), (), (), ())
    ob = make_observation(eb, 1)
    ob = Observation(ob.time, ob.vehicles, ("A",), (), (), (), (), ())
    d1 = decide(ea, oa, ControllerKind.FLEXIBILITY, horizon=20.0, forecast_customers=forecasts)
    d2 = decide(eb, ob, ControllerKind.FLEXIBILITY, horizon=20.0, forecast_customers=forecasts)
    vid = oa.vehicles[0].id
    assert d1.first_actions[vid].node_id == d2.first_actions[vid].node_id
    assert d1.first_actions[vid].purpose == d2.first_actions[vid].purpose
    r1 = [(v.node_id, v.purpose) for v in d1.routes.get(vid, [])]
    r2 = [(v.node_id, v.purpose) for v in d2.routes.get(vid, [])]
    # Strip any syn ids that differ only by planning clone; plant-relevant prefix should match.
    assert r1 == r2 or (
        [x for x in r1 if not str(x[0]).startswith("syn_")] == [x for x in r2 if not str(x[0]).startswith("syn_")]
    )


def test_duplicate_assignment_rejected_by_commitment_gate():
    inst = _toy()
    obs = make_observation(inst, 2)
    routes = {
        "v0": [Visit("A", "service")],
        "v1": [Visit("A", "service")],
    }
    assert not _routes_cover_commitments(inst, obs, routes, ["A"])


def test_robust_commitment_can_fail_when_nominal_passes():
    inst = _toy()
    obs = make_observation(inst, 1)
    # Construct a known nominal plan.
    plan_routes = {"v0": [Visit("A", "service")]}
    assert _routes_cover_commitments(inst, obs, plan_routes, ["A"])
    # Extreme energy scale should break coverage.
    assert not robust_routes_cover_commitments(inst, obs, plan_routes, ["A"], energy_scale=100.0, time_scale=1.0)


def test_stale_discard_when_optimize_overlaps_release():
    inst = _toy()
    result = run_sim_dynamic(
        inst,
        ControllerKind.MYOPIC,
        fleet_size=1,
        horizon=20.0,
        releases=[("A", 0.0), ("B", 1.0)],
        t_max=50.0,
        advance_plant_during_optimize=True,
        forced_optimize_seconds=5.0,
    )
    assert result.stale_discard_count >= 1


def test_exponential_gap_inverse_cdf():
    from safe_time_evrp.mpc3c.forecast import _exponential_gap

    g = _exponential_gap(2.0, 1.0 - math.exp(-1.0))
    assert abs(g - 2.0) < 1e-9
