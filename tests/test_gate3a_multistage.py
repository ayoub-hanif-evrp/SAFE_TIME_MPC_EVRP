"""Gate 3A: exact oracle, nonanticipativity, counterexamples, toy MPC."""

from __future__ import annotations

from safe_time_evrp.multistage.certificate import certify_state, terminal_viability_certificate
from safe_time_evrp.multistage.oracle import Status, evaluate_mode, feedback_feasible, open_loop_feasible
from safe_time_evrp.multistage.toy_mpc import compare_controllers, run_feedback_mpc
from safe_time_evrp.multistage.toys import (
    budget_reset_sensitive,
    feedback_useless,
    routing_fork_commitment,
    two_stage_charge_sufficient,
)


def test_routing_fork_open_loop_and_two_stage_fail_feedback_succeeds():
    inst = routing_fork_commitment()
    assert evaluate_mode(inst, "open_loop") is Status.PROVEN_INFEASIBLE
    assert evaluate_mode(inst, "two_stage") is Status.PROVEN_INFEASIBLE
    assert evaluate_mode(inst, "feedback") is Status.PROVEN_FEASIBLE
    assert evaluate_mode(inst, "clairvoyant") is Status.PROVEN_FEASIBLE


def test_budget_reset_creates_false_feasible():
    inst = budget_reset_sensitive()
    assert evaluate_mode(inst, "feedback") is Status.PROVEN_INFEASIBLE
    assert evaluate_mode(inst, "feedback_reset_budget") is Status.PROVEN_FEASIBLE


def test_feedback_useless_negative_control():
    inst = feedback_useless()
    assert evaluate_mode(inst, "open_loop") is Status.PROVEN_FEASIBLE
    assert evaluate_mode(inst, "feedback") is Status.PROVEN_FEASIBLE
    assert evaluate_mode(inst, "two_stage") is Status.PROVEN_FEASIBLE


def test_two_stage_charge_sufficient_negative_control_vs_han():
    inst = two_stage_charge_sufficient()
    assert evaluate_mode(inst, "open_loop") is Status.PROVEN_INFEASIBLE
    assert evaluate_mode(inst, "two_stage") is Status.PROVEN_FEASIBLE
    assert evaluate_mode(inst, "feedback") is Status.PROVEN_FEASIBLE


def test_nonanticipativity_feedback_ignores_future_mode_labels():
    """Swapping mode names without changing (time,energy,z) must not change feedback status."""
    inst = routing_fork_commitment()
    arcs = dict(inst.arcs)
    dj = arcs[("D", "J")]
    arcs[("D", "J")] = (
        dj[0].__class__(dj[0].time, dj[0].energy, dj[0].z, "renamed_low"),
        dj[1].__class__(dj[1].time, dj[1].energy, dj[1].z, "renamed_high"),
    )
    twin = inst.__class__(
        name=inst.name + "-renamed",
        nodes=inst.nodes,
        depot=inst.depot,
        chargers=inst.chargers,
        customers=inst.customers,
        windows=inst.windows,
        service=inst.service,
        arcs=arcs,
        battery=inst.battery,
        charge_rate=inst.charge_rate,
        gamma=inst.gamma,
        start_soc=inst.start_soc,
        start_time=inst.start_time,
        max_depth=inst.max_depth,
    )
    assert feedback_feasible(inst) == feedback_feasible(twin)


def test_residual_budget_update_blocks_second_high():
    inst = budget_reset_sensitive()
    assert open_loop_feasible(inst) is Status.PROVEN_INFEASIBLE
    assert feedback_feasible(inst, reset_budget=False) is Status.PROVEN_INFEASIBLE


def test_certificate_collapses_to_feedback_dp():
    inst = routing_fork_commitment()
    assert terminal_viability_certificate(inst) is Status.PROVEN_FEASIBLE
    cert = certify_state(inst)
    assert cert["novelty"] is False
    assert cert["method"] == "robust_bellman_labeling"


def test_toy_mpc_feedback_succeeds_on_both_routing_fork_worlds():
    inst = routing_fork_commitment()
    low = {a: modes[0] for a, modes in inst.arcs.items()}
    high = {a: modes[0] for a, modes in inst.arcs.items()}
    high[("D", "J")] = inst.arcs[("D", "J")][1]
    assert run_feedback_mpc(inst, low).success
    assert run_feedback_mpc(inst, high).success


def test_compare_controllers_routing_fork_gap():
    report = compare_controllers(routing_fork_commitment())
    assert report["oracle"]["open_loop"] == "proven_infeasible"
    assert report["oracle"]["two_stage"] == "proven_infeasible"
    assert report["oracle"]["feedback"] == "proven_feasible"
    # feedback MPC should succeed on every gamma-feasible scenario
    assert all(r["feedback_mpc"] for r in report["runs"])
