"""Preregistered structurally varied small networks (deterministic seeds)."""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.network import (
    ChargerSpec,
    CustomerSpec,
    RoadNetwork,
    Segment,
    make_single_ev_corridors,
)


@dataclass(frozen=True)
class SuiteInstance:
    instance_id: str
    net: RoadNetwork
    tags: tuple[str, ...]


def _corridor_family(
    *,
    name: str,
    battery: float,
    due_c: float,
    charge_time: float,
    useless_time: float,
    inform_time: float,
    exploit_time: float,
    energy_cost: float = 0.05,
    ac_base: float = 6.0,
    ac_phi1: float = 4.0,
    reward_c: float = 5.0,
    extra_first: tuple[Segment, ...] = (),
) -> RoadNetwork:
    segs = (
        Segment("DA_exploit", "D", "A", exploit_time, 4.0, 0.0),
        Segment("DA_inform", "D", "A", inform_time, 3.0, 3.0),
        Segment("DA_useless_inform", "D", "A", useless_time, 3.0, 3.0),
        *extra_first,
        Segment("AS", "A", "S", 1.0, 0.5, 0.0),
        Segment("SA", "S", "A", 1.0, 0.5, 0.0),
        Segment("AC", "A", "C", 8.0, ac_base, ac_phi1),
        Segment("CD", "C", "D", 5.0, 2.0, 0.0),
    )
    return RoadNetwork(
        name=name,
        nodes=("D", "A", "S", "C"),
        depot="D",
        battery=battery,
        segments=segs,
        customers=(
            CustomerSpec("cust_A", "A", 0.0, 100.0, 1.0, 10.0),
            CustomerSpec("cust_C", "C", 0.0, due_c, 1.0, reward_c),
        ),
        chargers=(ChargerSpec("chg_S", "S", charge_time),),
        energy_cost=energy_cost,
        metadata={"accepted_init": ("cust_A",), "optional": ("cust_C",), "suite": True},
    )


def build_preregistered_suite() -> list[SuiteInstance]:
    """Structurally varied instances — not a longer useless corridor only."""
    base = make_single_ev_corridors()
    out: list[SuiteInstance] = [
        SuiteInstance("S0_baseline", base, ("baseline", "three_first_actions")),
        SuiteInstance(
            "S1_tight_battery",
            _corridor_family(
                name="suite_tight_battery",
                battery=10.0,
                due_c=24.0,
                charge_time=15.0,
                useless_time=22.0,
                inform_time=12.0,
                exploit_time=10.0,
            ),
            ("battery_tight",),
        ),
        SuiteInstance(
            "S2_loose_deadline",
            _corridor_family(
                name="suite_loose_deadline",
                battery=12.0,
                due_c=50.0,
                charge_time=8.0,
                useless_time=22.0,
                inform_time=12.0,
                exploit_time=10.0,
            ),
            ("deadline_slack", "charge_enables_robust_C"),
        ),
        SuiteInstance(
            "S3_fast_charge",
            _corridor_family(
                name="suite_fast_charge",
                battery=12.0,
                due_c=24.0,
                charge_time=3.0,
                useless_time=22.0,
                inform_time=12.0,
                exploit_time=10.0,
            ),
            ("charging_speed",),
        ),
        SuiteInstance(
            "S4_late_obs",
            _corridor_family(
                name="suite_late_obs",
                battery=12.0,
                due_c=24.0,
                charge_time=15.0,
                useless_time=30.0,
                inform_time=18.0,  # observation after C due pressure
                exploit_time=10.0,
            ),
            ("observation_timing", "late_inform"),
        ),
        SuiteInstance(
            "S5_more_first_actions",
            _corridor_family(
                name="suite_more_first",
                battery=12.0,
                due_c=24.0,
                charge_time=15.0,
                useless_time=22.0,
                inform_time=12.0,
                exploit_time=10.0,
                extra_first=(
                    Segment("DA_mid_inform", "D", "A", 14.0, 3.2, 2.0),
                    Segment("DA_slow_exploit", "D", "A", 11.0, 4.2, 0.0),
                ),
            ),
            ("more_first_actions",),
        ),
        SuiteInstance(
            "S6_high_energy_cost",
            _corridor_family(
                name="suite_high_ec",
                battery=12.0,
                due_c=24.0,
                charge_time=15.0,
                useless_time=22.0,
                inform_time=12.0,
                exploit_time=10.0,
                energy_cost=0.25,
            ),
            ("energy_cost",),
        ),
        SuiteInstance(
            "S7_separable_regimes",
            _corridor_family(
                name="suite_sep",
                battery=12.0,
                due_c=26.0,
                charge_time=12.0,
                useless_time=22.0,
                inform_time=12.0,
                exploit_time=10.0,
                ac_base=5.0,
                ac_phi1=6.0,  # 5 vs 11 — sharper θ separation
            ),
            ("energy_regime_separability",),
        ),
    ]
    return out
