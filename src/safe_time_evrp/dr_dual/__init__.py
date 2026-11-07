"""Decision-relevant dual MPC for dynamic EVRP (long-lived research package).

Hypothesis: EVRP time-window / SOC / commitment structure yields a cheap sound
upper bound on action values that prunes operationally irrelevant information
gathering without losing the Bayes-optimal first action on tiny exact instances.
"""

from safe_time_evrp.dr_dual.bounds import DecisionRelevantBound, evaluate_bound
from safe_time_evrp.dr_dual.exact_oracle import ExactOracleResult, solve_exact
from safe_time_evrp.dr_dual.solver import PruningStats, solve_dr_dual

__all__ = [
    "DecisionRelevantBound",
    "ExactOracleResult",
    "PruningStats",
    "evaluate_bound",
    "solve_dr_dual",
    "solve_exact",
]
