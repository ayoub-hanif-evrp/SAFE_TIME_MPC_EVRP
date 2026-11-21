"""MSA-style consensus over first-action keys (Bent & Van Hentenryck)."""

from __future__ import annotations


def borda_consensus_scores(
    per_scenario_values: dict[str, list[float]],
) -> dict[str, float]:
    """Borda count: for each scenario, best value gets ``K`` points, worst 1.

    ``per_scenario_values[name][s]`` is the causal rollout value of candidate
    ``name`` under scenario ``s``. Missing / NaN-like entries are treated as
    very poor (``-1e300``).
    """
    if not per_scenario_values:
        return {}
    names = list(per_scenario_values.keys())
    n_sc = max(len(v) for v in per_scenario_values.values())
    if n_sc <= 0:
        return {n: 0.0 for n in names}
    k = len(names)
    scores = {n: 0.0 for n in names}
    for s in range(n_sc):
        ranked = sorted(
            names,
            key=lambda n: (
                per_scenario_values[n][s]
                if s < len(per_scenario_values[n])
                else -1e300
            ),
            reverse=True,
        )
        for rank, name in enumerate(ranked):
            scores[name] += float(k - rank)
    return scores


def apply_consensus_to_scored(
    scored: list[tuple],
    per_scenario_values: dict[str, list[float]],
) -> list[tuple]:
    """Reorder by Borda consensus; keep economic values intact for SPI.

    Expects scored items ``(value, name, cand, served, cls)``. Consensus only
    chooses the distinguished plan order — it must not overwrite J-scale values.
    """
    if not scored or not per_scenario_values:
        return scored
    cons = borda_consensus_scores(per_scenario_values)
    return sorted(scored, key=lambda it: (cons.get(it[1], 0.0), it[0]), reverse=True)
