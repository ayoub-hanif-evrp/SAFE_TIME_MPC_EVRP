"""Protocol v2: no announcement clamp; fleet cap explicit; env≠policy seeds."""

from __future__ import annotations

import pytest

from safe_time_evrp.data.dynamic_schneider import latest_feasible_announce_time, load_instance
from safe_time_evrp.data.dynamic_schneider_v2 import (
    generate_releases_v2,
    select_fleet_size_v2,
)
from safe_time_evrp.data.paths import schneider_dir

pytestmark = pytest.mark.skipif(
    not (schneider_dir() / "extracted").is_dir(),
    reason="Schneider archive not present",
)


def test_v2_does_not_clamp_releases_and_classifies_late():
    inst = load_instance("c101C5")
    releases, _, _, rule, classifications = generate_releases_v2(inst, environment_seed=12345, dynamicity="high")
    assert "clamp=none" in rule
    by_id = {c.customer_id: c for c in classifications}
    for cid, t in releases:
        assert by_id[cid].release_time == t
        latest = latest_feasible_announce_time(inst, cid)
        assert by_id[cid].late_for_depot_admit == (t > latest + 1e-12)


def test_v2_fleet_cap_is_explicit_and_higher_than_v1_six():
    inst = load_instance("c101_21")
    fleet, rule, meta = select_fleet_size_v2(inst)
    assert meta["hard_cap"] == 20
    assert fleet == min(20, meta["uncapped"])
    assert "hard_cap" in meta
    assert "min(20" in rule
