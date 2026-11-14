"""Regression tests for Schneider-derived dynamic EVRPTW seed semantics."""

from __future__ import annotations

import pytest

from safe_time_evrp.data.dynamic_schneider import (
    Dynamicity,
    build_dynamic_episode,
    generate_releases,
    latest_feasible_announce_time,
    list_schneider_refs,
    load_instance,
    require_verified_schneider_archive,
    stratified_split_small,
)
from safe_time_evrp.data.paths import schneider_dir


def _have_schneider() -> bool:
    try:
        require_verified_schneider_archive()
        return True
    except (FileNotFoundError, RuntimeError, OSError):
        return False


pytestmark = pytest.mark.skipif(not _have_schneider(), reason="Schneider archive not verified locally")


def test_stratified_split_covers_all_36_once():
    splits = stratified_split_small()
    all_stems = splits["train"] + splits["development"] + splits["test"]
    assert len(all_stems) == 36
    assert len(set(all_stems)) == 36
    small = {r.stem for r in list_schneider_refs(sizes=(5, 10, 15))}
    assert set(all_stems) == small


def test_environment_seed_controls_releases_not_policy_seed():
    stem = "c101C5"
    a = build_dynamic_episode(stem, environment_seed=11, policy_seed=1, dynamicity=Dynamicity.MEDIUM)
    b = build_dynamic_episode(stem, environment_seed=11, policy_seed=99, dynamicity=Dynamicity.MEDIUM)
    c = build_dynamic_episode(stem, environment_seed=12, policy_seed=1, dynamicity=Dynamicity.MEDIUM)
    assert a.releases == b.releases
    assert a.releases != c.releases
    assert a.known_at_start == b.known_at_start
    assert set(cid for cid, _ in a.releases) == set(load_instance(stem).customer_ids())


def test_announcements_respect_latest_admit_clamp():
    inst = load_instance("c101C5")
    releases, _, _, _ = generate_releases(inst, environment_seed=7, dynamicity=Dynamicity.HIGH)
    for cid, t in releases:
        assert t >= 0.0
        assert t <= latest_feasible_announce_time(inst, cid) + 1e-9


def test_dynamicity_changes_known_fraction_ordering():
    inst = load_instance("c101C10")
    low = generate_releases(inst, environment_seed=3, dynamicity=Dynamicity.LOW)
    high = generate_releases(inst, environment_seed=3, dynamicity=Dynamicity.HIGH)
    assert len(low[1]) >= len(high[1])  # known_at_start
    assert len(high[2]) >= len(low[2])  # dynamic_arrivals


def test_extracted_path_present():
    assert (schneider_dir() / "extracted").is_dir()
