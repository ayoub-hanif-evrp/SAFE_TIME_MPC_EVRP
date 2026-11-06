"""Exact Gate 3A toys. Each documents the intended open-loop / two-stage / feedback distinction."""

from __future__ import annotations

from safe_time_evrp.multistage.model import ArcMode, TinyInstance


def routing_fork_commitment() -> TinyInstance:
    """Open-loop and Han-style fixed-route two-stage fail; causal feedback succeeds.

    After D->J the plant reveals (time, SOC). Feedback may fork:

    - Low energy / slow D->J: arrive late with high SOC → must take direct J->C (detour misses due).
    - High energy / fast D->J: arrive early with low SOC → must take J->S->C with a unit charge
      (direct lacks energy).

    No single fixed travel sequence works for both worlds, so open-loop and two-stage
    adjustable-charge-on-fixed-route (Han-style) are infeasible, while nonanticipative
    feedback is feasible. This is the Gate B routing-fork gap.
    """
    return TinyInstance(
        name="routing_fork_commitment",
        nodes=("D", "J", "S", "C"),
        depot="D",
        chargers=frozenset({"S"}),
        customers=frozenset({"C"}),
        windows={"C": (0, 4)},
        service={"C": 0},
        arcs={
            ("D", "J"): (
                ArcMode(3, 2, 0, "low"),
                ArcMode(1, 7, 1, "high"),
            ),
            ("J", "C"): (ArcMode(1, 5, 0, "nom"),),
            ("J", "S"): (ArcMode(1, 1, 0, "nom"),),
            ("S", "C"): (ArcMode(1, 2, 0, "nom"),),
            ("C", "D"): (ArcMode(1, 1, 0, "nom"),),
        },
        battery=10,
        charge_rate=1,
        gamma=1,
        start_soc=10,
        start_time=0,
        max_depth=8,
    )


def budget_reset_sensitive() -> TinyInstance:
    """Illegal residual-budget reset creates a false feasible certificate.

    Both mandatory arcs spend z=1. With Gamma=1, true feedback cannot traverse both.
    Resetting Gamma after the first arc makes the same policy look feasible.
    """
    return TinyInstance(
        name="budget_reset_sensitive",
        nodes=("D", "A", "B"),
        depot="D",
        chargers=frozenset(),
        customers=frozenset({"A", "B"}),
        windows={"A": (0, 20), "B": (0, 20)},
        service={"A": 0, "B": 0},
        arcs={
            ("D", "A"): (ArcMode(1, 1, 1, "high"),),
            ("A", "B"): (ArcMode(1, 1, 1, "high"),),
            ("B", "D"): (ArcMode(1, 1, 0, "nom"),),
        },
        battery=10,
        charge_rate=1,
        gamma=1,
        start_soc=10,
        max_depth=6,
    )


def feedback_useless() -> TinyInstance:
    """Negative control: open-loop already feasible; feedback adds no feasibility value."""
    return TinyInstance(
        name="feedback_useless",
        nodes=("D", "C"),
        depot="D",
        chargers=frozenset(),
        customers=frozenset({"C"}),
        windows={"C": (0, 10)},
        service={"C": 0},
        arcs={
            ("D", "C"): (ArcMode(1, 1, 0, "nom"), ArcMode(1, 2, 1, "high")),
            ("C", "D"): (ArcMode(1, 1, 0, "nom"),),
        },
        battery=10,
        charge_rate=1,
        gamma=1,
        start_soc=10,
        max_depth=4,
    )


def two_stage_charge_sufficient() -> TinyInstance:
    """Negative control vs Han: fixed route + adjustable charge recovers feedback.

    Only travel sequence is D-J-C-D. J is a charger. Disturbance on D->J changes
    arrival SOC/time; wait-and-see charge at J restores feasibility. Open-loop with
    a single fixed charge fails (charge enough for high → late on slow low world);
    two-stage and feedback both succeed.
    """
    return TinyInstance(
        name="two_stage_charge_sufficient",
        nodes=("D", "J", "C"),
        depot="D",
        chargers=frozenset({"J"}),
        customers=frozenset({"C"}),
        windows={"C": (0, 4)},
        service={"C": 0},
        arcs={
            ("D", "J"): (
                ArcMode(2, 1, 0, "low"),
                ArcMode(1, 6, 1, "high"),
            ),
            ("J", "C"): (ArcMode(1, 3, 0, "nom"),),
            ("C", "D"): (ArcMode(1, 1, 0, "nom"),),
        },
        battery=10,
        charge_rate=1,
        gamma=1,
        start_soc=8,
        max_depth=6,
    )
