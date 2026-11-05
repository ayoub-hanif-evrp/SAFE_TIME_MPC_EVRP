import math

import pytest

from safe_time_evrp.data.checks import validate_instance
from safe_time_evrp.data.schneider import parse_schneider_text
from safe_time_evrp.environment.energy import DesignAssumptionEnergyBounds, ScaledNominalEnergy
from safe_time_evrp.environment.physics import evaluate_route
from safe_time_evrp.models.state import Anchor, Visit
from safe_time_evrp.optimization.exact_toy import make_reference_instance

SAMPLE = """
StringID   Type  x  y  demand ReadyTime DueDate ServiceTime
D0 d 0 0 0 0 100 0
S0 f 5 0 0 0 100 0
C1 c 10 0 1 0 40 2
C2 c 0 10 1 0 40 2

Q Vehicle fuel tank capacity /50/
C Vehicle load capacity /10/
r fuel consumption rate /1/
g inverse refueling rate /0.5/
v average Velocity /1/
"""


def test_parser_preserves_customers_and_directed_arcs():
    instance = parse_schneider_text(SAMPLE, "fixture", "memory")
    report = validate_instance(instance)
    assert report["ok"]
    assert report["customers"] == 2
    assert report["chargers"] == 1
    assert report["arcs"] == 4 * 3
    assert instance.arc("C1", "C2").distance == pytest.approx(math.hypot(10, -10))
    assert instance.arc("C1", "C2").energy == pytest.approx(instance.arc("C1", "C2").distance)
    assert ("C1", "C2") in instance.arcs and ("C2", "C1") in instance.arcs


def test_route_requires_energy_window_and_capacity():
    instance = make_reference_instance("easy")
    anchor = Anchor("D", 0.0, 50.0, 0.0, frozenset())
    ok = evaluate_route(instance, anchor, [Visit("C1", "service")])
    assert ok.feasible
    assert ok.served == ["C1"]
    tight = instance.with_recharge_policy("partial")
    partial = evaluate_route(
        tight,
        Anchor("D", 0.0, 20.0, 0.0, frozenset()),
        [Visit("S", "charge", charge_target=30.0), Visit("C1", "service")],
    )
    assert partial.feasible
    assert partial.end_soc < 30.0


def test_energy_bounds_are_labeled_as_assumptions():
    bounds = DesignAssumptionEnergyBounds(0.8, 1.2)
    assert bounds.as_record()["evidence"] == "design_assumption_not_calibrated"
    scaled = ScaledNominalEnergy(2.0)
    instance = make_reference_instance("easy")
    nominal = evaluate_route(instance, Anchor("D", 0, 50, 0, frozenset()), [Visit("C1", "service")])
    doubled = evaluate_route(
        instance,
        Anchor("D", 0, 50, 0, frozenset()),
        [Visit("C1", "service")],
        scaled,
    )
    assert doubled.feasible
    assert doubled.end_soc < nominal.end_soc
