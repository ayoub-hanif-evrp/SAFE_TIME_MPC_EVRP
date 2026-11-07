"""Safe dual MPC: belief updates, exact phenomenon, matched dual vs passive."""

from __future__ import annotations

from safe_time_evrp.dual_mpc.belief import BoundedErrorSet, DiscreteBelief
from safe_time_evrp.dual_mpc.controllers import DualControllerKind, matched_comparison, run_episode
from safe_time_evrp.dual_mpc.energy_param import ArcFeature, SharedThetaWorld
from safe_time_evrp.dual_mpc.exact_oracle import (
    FirstAction,
    run_exact_dual_example,
    verify_phenomenon_independent,
)
from safe_time_evrp.dual_mpc.mechanism import assess_mechanism


def test_belief_update_only_from_completed_observation():
    prior = DiscreteBelief.uniform((0.0, 1.0))
    feat = ArcFeature("inf", base=3.0, informative=3.0)
    world = SharedThetaWorld(theta_star=1.0)
    e = world.realize(feat)
    post = prior.update_from_observation(feat, e)
    assert abs(sum(post.probs) - 1.0) < 1e-12
    assert post.probs[1] > 0.99  # mass on theta=1


def test_uninformative_arc_does_not_update_belief():
    prior = DiscreteBelief.uniform((0.0, 1.0))
    feat = ArcFeature("exp", base=4.0, informative=0.0)
    post = prior.update_from_observation(feat, 4.0)
    assert post.probs == prior.probs


def test_bounded_error_set_update():
    s0 = BoundedErrorSet.from_bounds(0.0, 1.0)
    feat = ArcFeature("inf", base=3.0, informative=3.0)
    # observe e=6 => theta=1 exactly
    s1 = s0.update(feat, 6.0, eps_bar=0.0)
    assert s1.contains(1.0)
    assert not s1.contains(0.0)


def test_exact_dual_differs_from_passive_and_matches_manual():
    report = run_exact_dual_example()
    assert report.status.value == "EXACT"
    assert report.safe_passive_first is FirstAction.EXPLOIT
    assert report.safe_dual_first is FirstAction.INFORM
    assert report.information_changes_first_action
    assert report.commitment_safe
    v = verify_phenomenon_independent()
    assert v["values_match"]
    assert v["dual_selects_inform"]


def test_matched_episode_dual_beats_passive_on_mean_reward():
    cmp = matched_comparison()
    assert cmp["dual_minus_passive"] > 0
    assert cmp["passive_serves_c_frac"] == 0.0
    assert cmp["dual_serves_c_frac"] == 0.5  # only when theta=0


def test_controller_does_not_read_hidden_theta_for_decision():
    # Passive/dual decisions identical for both true thetas at first action.
    a0 = run_episode(DualControllerKind.SAFE_DUAL, 0.0)
    a1 = run_episode(DualControllerKind.SAFE_DUAL, 1.0)
    assert a0.first_action == a1.first_action == FirstAction.INFORM.value
    p0 = run_episode(DualControllerKind.SAFE_PASSIVE, 0.0)
    p1 = run_episode(DualControllerKind.SAFE_PASSIVE, 1.0)
    assert p0.first_action == p1.first_action == FirstAction.EXPLOIT.value


def test_mechanism_assessment_stops_for_human_decision():
    m = assess_mechanism()
    assert m.phenomenon_demonstrated
    assert m.new_theorem_proved is False
    assert m.reduces_to_known_safe_dual_control
    assert m.verdict == "STOP_HUMAN_DECISION"
