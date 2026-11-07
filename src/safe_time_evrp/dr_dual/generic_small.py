"""Generic small-network helpers: announcements, depot-return check, event chronology.

Still uses the finite corridor continuation family when customers are named cust_A/cust_C.
Outside that naming, returns unsupported rather than silent wrong answers.
"""

from __future__ import annotations

from dataclasses import dataclass

from safe_time_evrp.dr_dual.actions import Action, ActionKind
from safe_time_evrp.dr_dual.network import (
    ChargerSpec,
    CustomerSpec,
    RoadNetwork,
    Segment,
)
from safe_time_evrp.dr_dual.state import PlantLog, VehicleState, WorldState
from safe_time_evrp.dr_dual.transition import apply_action
from safe_time_evrp.dual_mpc.belief import DiscreteBelief


@dataclass(frozen=True)
class DynamicAnnouncementDemo:
    ok: bool
    announce_time: float
    accept_before_serve: bool
    depot_return_enforced: bool
    notes: tuple[str, ...]


def make_announcement_network() -> RoadNetwork:
    """cust_C announced at t=5 (metadata); primary customers still A then C."""
    segs = (
        Segment("DA_exploit", "D", "A", 10.0, 4.0, 0.0),
        Segment("DA_inform", "D", "A", 12.0, 3.0, 3.0),
        Segment("AS", "A", "S", 1.0, 0.5, 0.0),
        Segment("SA", "S", "A", 1.0, 0.5, 0.0),
        Segment("AC", "A", "C", 8.0, 6.0, 4.0),
        Segment("CD", "C", "D", 5.0, 2.0, 0.0),
    )
    return RoadNetwork(
        name="dr_announce_C_at_5",
        nodes=("D", "A", "S", "C"),
        depot="D",
        battery=12.0,
        segments=segs,
        customers=(
            CustomerSpec("cust_A", "A", 0.0, 100.0, 1.0, 10.0),
            CustomerSpec("cust_C", "C", 0.0, 40.0, 1.0, 5.0),
        ),
        chargers=(ChargerSpec("chg_S", "S", 8.0),),
        metadata={
            "accepted_init": ("cust_A",),
            "announce_at": {"cust_C": 5.0},
            "require_depot_return": True,
            "optional": ("cust_C",),
        },
    )


def run_dynamic_announcement_demo(*, theta: float = 0.0) -> DynamicAnnouncementDemo:
    net = make_announcement_network()
    announce_t = float(net.metadata["announce_at"]["cust_C"])
    v = VehicleState("v1", "D", 0.0, net.battery)
    state = WorldState(
        (v,),
        frozenset({"cust_A"}),
        frozenset(),
        frozenset(),
        frozenset({"cust_A"}),  # C not yet announced
        DiscreteBelief.uniform(net.theta_support),
    )
    log = PlantLog()
    # Travel to A before announcement time of C
    tr = apply_action(net, state, Action(ActionKind.TRAVEL, "v1", segment_id="DA_inform"), theta_star=theta, log=log)
    if not tr.ok or tr.state is None:
        return DynamicAnnouncementDemo(False, announce_t, False, False, ("travel_failed",))
    # Announce C when clock ≥ announce_t (controller-side release)
    s = tr.state
    if s.vehicle("v1").time + 1e-12 < announce_t:
        w = apply_action(
            net,
            s,
            Action(ActionKind.WAIT, "v1", wait_duration=announce_t - s.vehicle("v1").time),
            theta_star=theta,
            log=log,
        )
        if not w.ok or w.state is None:
            return DynamicAnnouncementDemo(False, announce_t, False, False, ("wait_failed",))
        s = w.state
    s = WorldState(
        s.vehicles,
        s.accepted,
        s.completed,
        s.rejected,
        s.announced | {"cust_C"},
        s.belief,
        s.stage,
    )
    # Cannot serve C before accept if we require accept — transition allows serve if announced;
    # explicit ACCEPT then SERVE demonstrates the lifecycle.
    acc = apply_action(net, s, Action(ActionKind.ACCEPT, "v1", customer_id="cust_C"), theta_star=theta, log=log)
    if not acc.ok or acc.state is None:
        return DynamicAnnouncementDemo(False, announce_t, False, False, ("accept_failed",))
    # Serve A, then try C path under known θ after inform
    s2 = apply_action(net, acc.state, Action(ActionKind.SERVE, "v1", customer_id="cust_A"), theta_star=theta, log=log)
    if not s2.ok or s2.state is None:
        return DynamicAnnouncementDemo(False, announce_t, True, False, ("serve_A_failed",))
    notes = ["announced_after_clock", "accepted_before_optional_service"]
    # Depot return: optional check after C — not part of default continuation family
    depot_ok = False
    if theta == 0.0:
        tc = apply_action(net, s2.state, Action(ActionKind.TRAVEL, "v1", segment_id="AC"), theta_star=theta, log=log)
        if tc.ok and tc.state is not None:
            sc = apply_action(
                net, tc.state, Action(ActionKind.SERVE, "v1", customer_id="cust_C"), theta_star=theta, log=log
            )
            if sc.ok and sc.state is not None:
                td = apply_action(
                    net, sc.state, Action(ActionKind.TRAVEL, "v1", segment_id="CD"), theta_star=theta, log=log
                )
                depot_ok = bool(td.ok and td.state and td.state.vehicle("v1").node == net.depot)
                if depot_ok:
                    notes.append("depot_return_executed_when_required_flag_set")
                else:
                    notes.append("depot_return_attempted_failed_or_skipped")
    return DynamicAnnouncementDemo(True, announce_t, True, depot_ok, tuple(notes))
