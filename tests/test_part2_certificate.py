"""Exact and adversarial checks for the rectangular route certificate."""

from __future__ import annotations

from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.instance import (
    Instance,
    Node,
    NodeKind,
    TimeWindow,
    VehicleType,
    build_euclidean_instance,
)
from safe_time_evrp.models.state import Anchor, Observation, VehicleView, Visit
from safe_time_evrp.robust.certificate import (
    IncrementalCache,
    Verdict,
    propagate,
    propagate_incremental,
    upper_corner_feasible,
)
from safe_time_evrp.robust.uncertainty import RectangularUncertainty, scale_instance


def _instance(battery: float, nodes: list[Node], name: str) -> Instance:
    vehicle = VehicleType(battery, 10.0, 1.0, 1.0, 1.0, "full")
    return build_euclidean_instance(name, nodes, vehicle, source_format="synthetic", source_name=name)


def _anchor(instance: Instance, soc: float | None = None, time: float = 0.0) -> Anchor:
    return Anchor(
        instance.depot_id,
        time,
        instance.vehicle_type.battery_capacity if soc is None else soc,
        0.0,
        frozenset(),
    )


def _window(due: float) -> TimeWindow:
    return TimeWindow(0.0, due)


def _nodes(due_a: float, b: tuple[float, float]) -> list[Node]:
    return [
        Node("D", NodeKind.DEPOT, 0, 0, 0, _window(500), 0),
        Node("S", NodeKind.CHARGER, 1, 1, 0, _window(500), 0),
        Node("A", NodeKind.CUSTOMER, 10, 0, 1, _window(due_a), 1),
        Node("B", NodeKind.CUSTOMER, b[0], b[1], 1, _window(500), 1),
    ]


def test_upper_corner_matches_independent_physics():
    instance = _instance(40, _nodes(400, (10, 10)), "match")
    uncertainty = RectangularUncertainty(0.8, 1.25, 0.8, 1.25)
    visits = [Visit("A", "service")]
    certificate = propagate(instance, _anchor(instance), visits, uncertainty)
    assert certificate.verdict is Verdict.CERTIFIED_FEASIBLE
    assert upper_corner_feasible(instance, _anchor(instance), visits, uncertainty)


def test_case_a_nominal_insertion_is_not_robust():
    instance = _instance(40, _nodes(400, (10, 10)), "case-a")
    uncertainty = RectangularUncertainty(1.0, 1.3, 1.0, 1.3, evidence="design_assumption")
    direct = propagate(instance, _anchor(instance), [Visit("A", "service")], uncertainty)
    detour = [Visit("B", "service"), Visit("A", "service")]
    nominal = evaluate_route(instance, _anchor(instance), detour)
    robust = propagate(instance, _anchor(instance), detour, uncertainty)
    assert nominal.feasible
    assert direct.verdict is Verdict.CERTIFIED_FEASIBLE
    assert robust.verdict is Verdict.CERTIFIED_INFEASIBLE
    assert robust.critical_constraint == "battery_floor"
    assert upper_corner_feasible(instance, _anchor(instance), detour, uncertainty) is False


def test_case_b_time_window_under_travel_uncertainty():
    instance = _instance(100, _nodes(25, (3, 4)), "case-b")
    uncertainty = RectangularUncertainty(1.0, 2.0, 1.0, 1.0)
    detour = [Visit("B", "service"), Visit("A", "service")]
    nominal = evaluate_route(instance, _anchor(instance), detour)
    robust = propagate(instance, _anchor(instance), detour, uncertainty)
    assert nominal.feasible
    assert robust.verdict is Verdict.CERTIFIED_INFEASIBLE
    assert robust.critical_constraint == "missed_window"


def test_case_e_tightening_is_conservative():
    instance = _instance(30, _nodes(400, (10, 10)), "case-e")
    uncertainty = RectangularUncertainty(1.0, 1.2, 1.0, 1.2)
    visits = [Visit("A", "service")]
    exact = propagate(instance, _anchor(instance), visits, uncertainty)
    tightened = propagate(instance, _anchor(instance), visits, uncertainty, energy_inflation=1.5)
    assert exact.verdict is Verdict.CERTIFIED_FEASIBLE
    assert upper_corner_feasible(instance, _anchor(instance), visits, uncertainty)
    assert tightened.verdict is Verdict.CERTIFIED_INFEASIBLE
    assert tightened.model == "tightened_rectangle"


def test_case_g_proved_infeasible_is_not_unknown():
    instance = _instance(5, _nodes(400, (1, 0)), "case-g")
    uncertainty = RectangularUncertainty()
    certificate = propagate(instance, _anchor(instance), [Visit("A", "service")], uncertainty)
    assert certificate.verdict is Verdict.CERTIFIED_INFEASIBLE
    assert certificate.critical_constraint == "battery_floor"


def test_case_h_disturbance_outside_the_rectangle_breaks_the_guarantee():
    instance = _instance(30, _nodes(400, (1, 0)), "case-h")
    uncertainty = RectangularUncertainty(1.0, 1.1, 1.0, 1.1)
    visits = [Visit("A", "service")]
    certificate = propagate(instance, _anchor(instance), visits, uncertainty)
    assert certificate.verdict is Verdict.CERTIFIED_FEASIBLE
    outside = scale_instance(instance, time_factor=1.0, energy_factor=2.0)
    realized = evaluate_route(outside, _anchor(instance), visits)
    assert realized.feasible is False
    assert realized.reason == "battery_depleted"


def test_nonmonotone_model_is_unknown():
    instance = _instance(40, _nodes(400, (1, 0)), "unknown")
    uncertainty = RectangularUncertainty(monotone_linear=False)
    certificate = propagate(instance, _anchor(instance), [Visit("A", "service")], uncertainty)
    assert certificate.verdict is Verdict.UNKNOWN
    assert certificate.critical_constraint == "nonmonotone_dynamics"


def test_shift_preserves_suffix_inside_the_rectangle():
    instance = _instance(40, _nodes(400, (1, 0)), "shift")
    uncertainty = RectangularUncertainty(1.0, 1.2, 1.0, 1.2)
    whole = propagate(instance, _anchor(instance), [Visit("A", "service")], uncertainty)
    assert whole.verdict is Verdict.CERTIFIED_FEASIBLE
    realized = evaluate_route(instance, _anchor(instance), [Visit("A", "service")])
    shifted = Anchor(realized.end_node, realized.end_time, realized.end_soc, realized.end_load, frozenset())
    suffix = propagate(instance, shifted, [Visit("D", "return")], uncertainty)
    assert suffix.verdict is Verdict.CERTIFIED_FEASIBLE


def test_incremental_prefix_matches_full_propagation():
    instance = _instance(80, _nodes(400, (3, 4)), "prefix")
    uncertainty = RectangularUncertainty(1.0, 1.1, 1.0, 1.1)
    anchor = _anchor(instance)
    first = [Visit("B", "service"), Visit("A", "service")]
    cache = IncrementalCache()
    full = propagate_incremental(instance, anchor, first, uncertainty, cache)
    changed = [Visit("B", "service"), Visit("S", "charge"), Visit("A", "service")]
    again = propagate_incremental(instance, anchor, changed, uncertainty, cache)
    reference = propagate(instance, anchor, changed, uncertainty)
    assert cache.hits == 1
    assert full.verdict is reference.verdict or again.verdict is reference.verdict
    assert again.verdict is reference.verdict
    assert again.critical_constraint == reference.critical_constraint


def test_rejected_request_does_not_change_a_certified_route():
    instance = _instance(40, _nodes(400, (10, 10)), "reject")
    uncertainty = RectangularUncertainty(1.0, 1.3, 1.0, 1.3)
    anchor = _anchor(instance)
    kept = propagate(instance, anchor, [Visit("A", "service")], uncertainty)
    assert kept.verdict is Verdict.CERTIFIED_FEASIBLE
    view = VehicleView("v1", "idle", "D", 40, 0, (), anchor, None)
    observation = Observation(0, (view,), ("A", "B"), ("A",), (), (), (), ())
    from safe_time_evrp.robust.certificate import certify

    certified = certify(
        observed_state=observation,
        committed_routes={"v1": [Visit("A", "service")]},
        uncertainty_set=uncertainty,
        instance=instance,
    )
    assert certified.verdict is Verdict.CERTIFIED_FEASIBLE
    omitted = certify(
        observed_state=observation,
        committed_routes={"v1": []},
        uncertainty_set=uncertainty,
        instance=instance,
    )
    assert omitted.verdict is Verdict.CERTIFIED_INFEASIBLE
    assert omitted.critical_constraint == "commitment_omitted"
