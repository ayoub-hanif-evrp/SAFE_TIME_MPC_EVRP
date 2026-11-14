"""Phase 3F: admission semantics, switching distinctness, gate smoke."""

from __future__ import annotations

from pathlib import Path

from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.mpc_central.counterfactual_actions import (
    eligible_new_accepts,
    generate_counterfactual_actions,
    sanitize_newly_accepted,
    sanitize_routes,
)
from safe_time_evrp.mpc_central.forks import case_a_predictive_charging_fork
from safe_time_evrp.mpc_central.phase3f_gate import reproduce_in_service_admission_bug, run_phase3f
from safe_time_evrp.mpc_central.switching_mpc import CommitmentViabilitySwitchingMpc


def _obs_with_in_service_and_idle(spec) -> Observation:
    bat = spec.instance.vehicle_type.battery_capacity
    v1 = VehicleView(
        "v1",
        "serving",
        "Near",
        bat - 1.0,
        0.0,
        ("Near",),
        Anchor("Near", 5.0, bat - 1.0, 0.0, frozenset({"Near"})),
        "Near",
    )
    v2 = VehicleView(
        "v2",
        "idle",
        spec.instance.depot_id,
        bat,
        0.0,
        (),
        Anchor(spec.instance.depot_id, 5.0, bat, 0.0, frozenset()),
        None,
    )
    return Observation(
        time=5.0,
        vehicles=(v1, v2),
        released_open=("Near", "Far"),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=("Near",),
        deferred=(),
    )


def test_eligible_new_accepts_excludes_in_service():
    spec = case_a_predictive_charging_fork()
    obs = _obs_with_in_service_and_idle(spec)
    eligible = eligible_new_accepts(obs)
    assert "Near" not in eligible
    assert "Far" in eligible


def test_counterfactuals_do_not_reaccept_or_redispatch_in_service():
    spec = case_a_predictive_charging_fork()
    # Augment instance is single-vehicle in fork; still exercise filters on synthetic 2-veh obs
    # using the fork instance nodes only (Far may be hidden from public snapshot — use Near-only).
    obs = Observation(
        time=5.0,
        vehicles=(
            VehicleView(
                "v1",
                "serving",
                "Near",
                10.0,
                0.0,
                ("Near",),
                Anchor("Near", 5.0, 10.0, 0.0, frozenset({"Near"})),
                "Near",
            ),
            VehicleView(
                "v2",
                "idle",
                "D",
                16.0,
                0.0,
                (),
                Anchor("D", 5.0, 16.0, 0.0, frozenset()),
                None,
            ),
        ),
        released_open=("Near",),
        accepted=(),
        completed=(),
        rejected=(),
        in_service=("Near",),
        deferred=(),
    )
    assert sanitize_newly_accepted(obs, ["Near"]) == []
    cleaned = sanitize_routes(obs, {"v1": [], "v2": [Visit("Near", "service")]})
    assert cleaned["v2"] == []
    cands, _ = generate_counterfactual_actions(
        spec.instance, obs, horizon=80.0, alns_iterations=4, alns_time=0.05, seed=0, include_b1=False
    )
    for _name, d in cands:
        assert "Near" not in d.newly_accepted
        for visits in d.routes.values():
            assert all(not (v.purpose == "service" and v.node_id == "Near") for v in visits)


def test_plant_admission_probe_passes():
    report = reproduce_in_service_admission_bug("A_low_soc_charge", seed=7)
    assert report["reproduced_state"] is True
    assert report["pass"] is True
    assert report["bad_newly_accepted"] == []
    assert report["bad_service_legs_to_in_service"] == []


def test_switching_controller_defaults_to_b1_without_forecast():
    spec = case_a_predictive_charging_fork()
    ctrl = CommitmentViabilitySwitchingMpc(
        spec.instance,
        80.0,
        forecast=None,
        use_forecast=False,
        allow_switching=True,
        alns_iterations=6,
        time_limit_seconds=0.25,
        seed=0,
    )
    d = ctrl.decide(spec.observation, "test")
    assert "commitment_viability_switching_mpc" in d.notes
    assert ctrl.profile.b1_defaults >= 1


def test_run_phase3f_writes_artifact(tmp_path: Path):
    art = run_phase3f(out_dir=tmp_path)
    assert (tmp_path / "phase3f_results.json").is_file()
    assert art["gate"]["decision"] in {"GO_PROTOTYPE", "REVISE", "NO-GO"}
    assert art["admission_repair"]["pass"] is True
