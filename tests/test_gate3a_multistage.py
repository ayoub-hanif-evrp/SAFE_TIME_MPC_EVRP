"""Gate 3A/3B: exact oracle, nonanticipativity, counterexamples, toy MPC."""

from __future__ import annotations

from safe_time_evrp.multistage.certificate import certify_state, terminal_viability_certificate
from safe_time_evrp.multistage.oracle import (
    Status,
    admissible_path_combos,
    evaluate_mode,
    feedback_feasible,
    open_loop_feasible,
    path_combo_admissible,
)
from safe_time_evrp.multistage.toy_mpc import compare_controllers, run_feedback_mpc
from safe_time_evrp.multistage.toys import (
    budget_reset_sensitive,
    feedback_useless,
    routing_fork_commitment,
    standard_budgeted_has_nominal,
    two_stage_charge_sufficient,
)


def test_routing_fork_open_loop_and_two_stage_fail_feedback_succeeds():
    inst = routing_fork_commitment()
    assert evaluate_mode(inst, "open_loop") is Status.PROVEN_INFEASIBLE
    assert evaluate_mode(inst, "two_stage") is Status.PROVEN_INFEASIBLE
    assert evaluate_mode(inst, "feedback") is Status.PROVEN_FEASIBLE
    assert evaluate_mode(inst, "clairvoyant") is Status.PROVEN_FEASIBLE


def test_pathological_budget_reset_probe_preserved_but_withdrawn():
    """Gate 3A behavior retained as pathological probe; not a standard budgeted CEX."""
    inst = budget_reset_sensitive()
    assert inst.name.endswith("pathological")
    assert evaluate_mode(inst, "feedback") is Status.PROVEN_INFEASIBLE
    assert evaluate_mode(inst, "feedback_reset_budget") is Status.PROVEN_FEASIBLE


def test_standard_budgeted_nominal_keeps_feedback_feasible():
    inst = standard_budgeted_has_nominal()
    assert evaluate_mode(inst, "feedback") is Status.PROVEN_FEASIBLE
    assert evaluate_mode(inst, "open_loop") is Status.PROVEN_FEASIBLE
    # Double-high is outside the uncertainty set and must not force infeasibility.
    highs = (inst.arcs[("D", "A")][1], inst.arcs[("A", "B")][1])
    assert not path_combo_admissible(highs, inst.gamma)


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


def test_nonanticipativity_identical_observation_histories_same_action():
    """Two scenarios that land in the same information state must admit the same action set."""
    from safe_time_evrp.multistage.oracle import apply_travel, initial_state, legal_travel, state_key
    from safe_time_evrp.multistage.toy_mpc import pick_feedback_action

    inst = routing_fork_commitment()
    # Construct an alternate world whose first-arc outcome matches the low world's observables
    # by using an identical (time,energy,z) mode with a different label — same observation.
    low = inst.arcs[("D", "J")][0]
    twin_mode = low.__class__(low.time, low.energy, low.z, "alias_low")
    root = initial_state(inst)
    child_a = apply_travel(inst, root, "J", low)
    child_b = apply_travel(inst, root, "J", twin_mode)
    assert child_a is not None and child_b is not None
    assert state_key(child_a) == state_key(child_b)
    assert pick_feedback_action(inst, child_a) == pick_feedback_action(inst, child_b)
    # Action may only depend on legal travels from that shared state.
    assert legal_travel(inst, child_a) == legal_travel(inst, child_b)


def test_residual_budget_pathological_probe_still_blocks_second_high():
    inst = budget_reset_sensitive()
    assert open_loop_feasible(inst) is Status.PROVEN_INFEASIBLE
    assert feedback_feasible(inst, reset_budget=False) is Status.PROVEN_INFEASIBLE


def test_open_loop_skips_budget_exceeding_histories():
    inst = standard_budgeted_has_nominal()
    mode_lists = [list(inst.arcs[("D", "A")]), list(inst.arcs[("A", "B")])]
    all_combos = list(__import__("itertools").product(*mode_lists))
    adm = admissible_path_combos(mode_lists, inst.gamma)
    assert len(adm) < len(all_combos)
    assert all(path_combo_admissible(c, inst.gamma) for c in adm)


def test_search_cap_returns_time_limit_not_infeasible(monkeypatch):
    import safe_time_evrp.multistage.oracle as oracle_mod

    monkeypatch.setattr(oracle_mod, "OPEN_LOOP_PREFIX_CAP", 1)
    # Cap of 1: evaluate empty plan then stop with pending extensions → TIME_LIMIT
    inst = routing_fork_commitment()
    status = oracle_mod.open_loop_feasible(inst)
    assert status is Status.TIME_LIMIT


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
    assert all(r["feedback_mpc"] for r in report["runs"])
