from safe_time_evrp.evaluation.dynamic import (
    independent_parent_scenarios,
    indexed_stagger,
    lead_time_releases,
    poisson_pool_releases,
    uniform_releases,
)
from safe_time_evrp.optimization.exact_toy import (
    enumerate_case,
    forced_first_travel,
    make_reference_instance,
)


def test_exact_family_labels_are_not_generalized():
    easy = enumerate_case("easy")
    assert easy.best_served == 3
    assert easy.heuristic_served == 3
    assert easy.heuristic_status.startswith("heuristic_")
    charged = enumerate_case("needs_two_charges", fleet_size=1)
    assert charged.feasible_exists
    assert charged.best_served == 1
    assert charged.heuristic_served == 0
    assert charged.heuristic_status == "heuristic_missed_a_proven_feasible_route"
    impossible = enumerate_case("impossible_window")
    assert impossible.best_served == 1
    assert impossible.heuristic_served == 1
    assert forced_first_travel("impossible_window", "C1", "C1") == "proven_infeasible"
    assert forced_first_travel("needs_two_charges", "C1", "S") == "proven_feasible"
    assert forced_first_travel("needs_two_charges", "C1", "C1") == "proven_infeasible"


def test_release_mechanisms_do_not_share_geometries_or_future_fields():
    easy = make_reference_instance("easy")
    other = make_reference_instance("impossible_window")
    stagger = indexed_stagger(easy, step=10)
    assert [item[1] for item in stagger.releases] == [0, 10, 20]
    assert "C3" in stagger.hidden_at(0)
    uniform_a = uniform_releases(easy, seed=1, release_horizon=50)
    uniform_b = uniform_releases(easy, seed=1, release_horizon=50)
    uniform_c = uniform_releases(easy, seed=2, release_horizon=50)
    assert uniform_a.releases == uniform_b.releases
    assert uniform_a.releases != uniform_c.releases
    lead = lead_time_releases(easy, seed=3, lead_min=1, lead_max=5)
    assert all(release <= easy.node(cid).window.ready for cid, release in lead.releases)
    poisson = poisson_pool_releases(
        easy,
        seed=4,
        horizon=40,
        rates=[(0, 20, 0.2), (20, 40, 0.05)],
    )
    assert poisson.mechanism == "poisson_pool"
    assert len(poisson.releases) <= 3
    parents = independent_parent_scenarios([easy, other], seed=7, release_horizon=15)
    assert parents[0].parent_instance != parents[1].parent_instance
    assert easy.node("C2").x != other.node("C2").x or easy.node("C2").y != other.node("C2").y
