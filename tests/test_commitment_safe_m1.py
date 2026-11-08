"""Incremental resource profiles and M1 certificate-carrying MPC."""

from __future__ import annotations

from safe_time_evrp.commitment_safe_mpc.alns_mpc import ReactiveAlnsMpc
from safe_time_evrp.commitment_safe_mpc.m1_mpc import CertificateCarryingAlnsMpc
from safe_time_evrp.commitment_safe_mpc.route_resource_profile import (
    EvalMode,
    EvalStats,
    evaluate_with_profile,
)
from safe_time_evrp.controllers.episode import run_episode
from safe_time_evrp.environment.energy import NominalLinearEnergy
from safe_time_evrp.models.instance import Node, NodeKind, TimeWindow, VehicleType, build_euclidean_instance
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.optimization.exact_toy import make_reference_instance
from safe_time_evrp.validation.replay import validate_log


def _obs(inst, released, fleet=2):
    bat = inst.vehicle_type.battery_capacity
    vs = []
    for i in range(fleet):
        a = Anchor(inst.depot_id, 0.0, bat, 0.0, frozenset())
        vs.append(VehicleView(f"v{i + 1}", "idle", inst.depot_id, bat, 0.0, (), a, None))
    return Observation(0.0, tuple(vs), released, (), (), (), (), ())


def test_incremental_agrees_with_full_on_supported_routes():
    inst = make_reference_instance("easy")
    obs = _obs(inst, ("C1", "C2"), fleet=1)
    energy = NominalLinearEnergy()
    visits = [Visit("C1", "service"), Visit("C2", "service")]
    stats_full = EvalStats()
    full_res, full_prof = evaluate_with_profile(
        inst, obs.vehicles[0].anchor, visits, energy=energy, mode=EvalMode.FULL_EVALUATION, stats=stats_full
    )
    assert full_res.feasible and full_prof is not None
    # Mutate suffix: drop C2
    visits2 = [Visit("C1", "service")]
    stats_inc = EvalStats()
    inc_res, _ = evaluate_with_profile(
        inst,
        obs.vehicles[0].anchor,
        visits2,
        energy=energy,
        mode=EvalMode.INCREMENTAL_EVALUATION,
        previous=full_prof,
        stats=stats_inc,
    )
    full2, _ = evaluate_with_profile(
        inst, obs.vehicles[0].anchor, visits2, energy=energy, mode=EvalMode.FULL_EVALUATION
    )
    assert inc_res.feasible == full2.feasible
    assert set(inc_res.served) == set(full2.served)
    assert abs(inc_res.distance - full2.distance) < 1e-9
    assert stats_inc.incremental_evals + stats_inc.full_evals >= 1


def test_m1_episode_replays():
    inst = make_reference_instance("easy")
    ctrl = CertificateCarryingAlnsMpc(inst, 200, iterations=25, time_limit_seconds=0.3, seed=3)
    result = run_episode(
        inst,
        [("C1", 0.0), ("C2", 0.0), ("C3", 30.0)],
        fleet_size=2,
        horizon=200,
        max_replan_interval=40,
        t_max=200,
        controller=ctrl,
    )
    assert validate_log(inst, result.log).ok
    assert ctrl.profile.decisions >= 1


def test_m1_ablation_flags():
    inst = make_reference_instance("easy")
    no_reuse = CertificateCarryingAlnsMpc(
        inst, 200, iterations=10, time_limit_seconds=0.1, seed=1, reuse_certificates=False
    )
    no_incr = CertificateCarryingAlnsMpc(
        inst,
        200,
        iterations=10,
        time_limit_seconds=0.1,
        seed=1,
        eval_mode=EvalMode.FULL_EVALUATION,
        reuse_certificates=True,
    )
    obs = _obs(inst, ("C1", "C2", "C3"))
    d1 = no_reuse.decide(obs, "t")
    d2 = no_incr.decide(obs, "t")
    assert d1.audit["m1"]["reuse_certificates"] is False
    assert d2.audit["m1"]["eval_mode"] == "FULL_EVALUATION"


def test_alns_incremental_mode_runs():
    vehicle = VehicleType(500.0, 2.0, 1.0, 1.0, 1.0, "full")
    nodes = [
        Node("D", NodeKind.DEPOT, 0, 0, 0, TimeWindow(0, 5000), 0),
        Node("S", NodeKind.CHARGER, 0, 1, 0, TimeWindow(0, 5000), 0),
        Node("A", NodeKind.CUSTOMER, 5, 0, 1, TimeWindow(0, 40), 1),
        Node("B", NodeKind.CUSTOMER, 0, 5, 1, TimeWindow(0, 45), 1),
        Node("C", NodeKind.CUSTOMER, 50, 0, 2, TimeWindow(0, 55), 1),
    ]
    inst = build_euclidean_instance(
        "m1pack", nodes, vehicle, source_format="synthetic", source_name="t", assumptions=()
    )
    obs = _obs(inst, ("A", "B", "C"), fleet=2)
    ctrl = ReactiveAlnsMpc(
        inst,
        400,
        iterations=80,
        time_limit_seconds=2.0,
        seed=0,
        destroy_fraction=0.85,
        eval_mode=EvalMode.INCREMENTAL_EVALUATION,
    )
    d = ctrl.decide(obs, "t")
    assert set(d.planned_service) == {"A", "B", "C"}
    assert d.audit["alns"]["eval_mode"] == "INCREMENTAL_EVALUATION"
