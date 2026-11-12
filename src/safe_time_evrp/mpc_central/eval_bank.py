"""Instrumented scenario-evaluation bank for matched-budget MPC comparisons.

Rules
-----
- Every unique (action, scenario_index) plant rollout is computed at most once.
- The first computation increments ``n_evals`` (the scarce budget resource).
- Cache hits do not consume budget.
- Online policies must never call the offline oracle; use ``OfflineOracle`` separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from safe_time_evrp.mpc_central.causal_plant import PlantEpisodeScore, evaluate_action_scenario
from safe_time_evrp.mpc_central.forks import ForkSpec


@dataclass
class EvalBank:
    spec: ForkSpec
    n_evals: int = 0
    wall_seconds: float = 0.0
    _cache: dict[tuple[str, int], PlantEpisodeScore] = field(default_factory=dict)
    _oracle_calls_forbidden: bool = True

    def evaluate(self, action: str, scenario_index: int) -> PlantEpisodeScore:
        key = (action, int(scenario_index))
        if key in self._cache:
            return self._cache[key]
        if action not in self.spec.candidate_actions:
            raise KeyError(f"action {action} not in candidate set")
        if scenario_index < 0 or scenario_index >= len(self.spec.scenarios):
            raise IndexError(f"scenario_index {scenario_index} out of range")
        t0 = perf_counter()
        score = evaluate_action_scenario(
            self.spec,
            action,
            self.spec.scenarios[scenario_index],
            scenario_index=scenario_index,
        )
        self.wall_seconds += perf_counter() - t0
        self.n_evals += 1
        self._cache[key] = score
        return score

    def cached_value(self, action: str, scenario_index: int) -> float | None:
        hit = self._cache.get((action, int(scenario_index)))
        return None if hit is None else hit.value

    def sampled_expectation(self, action: str, *, missing_fill: float = 0.0) -> float | None:
        """Estimate E[V] with fixed prior fill for unsampled scenarios (no renormalization).

        For each scenario k:
          - if sampled: use the cached plant value
          - if not: use ``missing_fill`` (default 0 = no credit for unseen futures)

        This is intentionally conservative and order-transparent. It is **not** an
        unbiased estimator of the full expectation unless every scenario is sampled.
        Returns None only when the action has never been evaluated at all.
        """
        if not any((action, k) in self._cache for k in range(len(self.spec.scenarios))):
            return None
        total = 0.0
        for k, p in enumerate(self.spec.scenario_probs):
            if (action, k) in self._cache:
                total += p * self._cache[(action, k)].value
            else:
                total += p * missing_fill
        return total

    def sampled_indices(self, action: str) -> tuple[int, ...]:
        return tuple(k for k in range(len(self.spec.scenarios)) if (action, k) in self._cache)


@dataclass
class OfflineOracle:
    """Offline exhaustive truth — must not be used inside online budgeted policies."""

    spec: ForkSpec
    values: dict[str, float] = field(default_factory=dict)
    per_scenario: dict[str, tuple[float, ...]] = field(default_factory=dict)
    n_oracle_evals: int = 0

    @classmethod
    def build(cls, spec: ForkSpec) -> OfflineOracle:
        oracle = cls(spec=spec)
        for action in spec.candidate_actions:
            vals = []
            for k, sc in enumerate(spec.scenarios):
                score = evaluate_action_scenario(spec, action, sc, scenario_index=k)
                oracle.n_oracle_evals += 1
                vals.append(score.value)
            oracle.per_scenario[action] = tuple(vals)
            oracle.values[action] = sum(p * v for p, v in zip(spec.scenario_probs, vals, strict=True))
        return oracle

    def best_action(self) -> str:
        return max(self.values, key=lambda a: (self.values[a], a))
