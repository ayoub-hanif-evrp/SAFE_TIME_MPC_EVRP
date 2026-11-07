"""Global computation counters for bound/oracle work (not just first-action expansions)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ComputeCounters:
    known_theta_continuation_calls: int = 0
    common_policy_evaluations: int = 0
    bayes_continuation_calls: int = 0
    bound_evaluations: int = 0
    resource_bound_evaluations: int = 0
    transition_calls: int = 0

    def reset(self) -> None:
        self.known_theta_continuation_calls = 0
        self.common_policy_evaluations = 0
        self.bayes_continuation_calls = 0
        self.bound_evaluations = 0
        self.resource_bound_evaluations = 0
        self.transition_calls = 0

    def as_dict(self) -> dict:
        return {
            "known_theta_continuation_calls": self.known_theta_continuation_calls,
            "common_policy_evaluations": self.common_policy_evaluations,
            "bayes_continuation_calls": self.bayes_continuation_calls,
            "bound_evaluations": self.bound_evaluations,
            "resource_bound_evaluations": self.resource_bound_evaluations,
            "transition_calls": self.transition_calls,
            "total_heavy_calls": (
                self.known_theta_continuation_calls
                + self.common_policy_evaluations
                + self.bayes_continuation_calls
                + self.bound_evaluations
                + self.resource_bound_evaluations
            ),
        }


COUNTERS = ComputeCounters()
