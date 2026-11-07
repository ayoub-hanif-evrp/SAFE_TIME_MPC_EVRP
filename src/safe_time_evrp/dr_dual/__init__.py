"""Decision-relevant dual MPC for dynamic EVRP (long-lived research package).

Hypothesis: EVRP time-window / SOC / commitment structure yields a cheap sound
upper bound on action values that prunes operationally irrelevant information
gathering without losing the Bayes-optimal first action on tiny exact instances.
"""

from safe_time_evrp.dr_dual.bounds import DecisionRelevantBound, evaluate_bound
from safe_time_evrp.dr_dual.common_policy import abstract_p1_p2_counterexample, select_common_policy
from safe_time_evrp.dr_dual.exact_oracle import ExactOracleResult, solve_exact
from safe_time_evrp.dr_dual.fleet_oracle import solve_exact_two_ev_nonanticipative
from safe_time_evrp.dr_dual.solver import (
    PruningStats,
    solve_dr_dual,
    solve_info_gain_heuristic,
    solve_passive_mpc,
    solve_robust_mpc,
)

__all__ = [
    "DecisionRelevantBound",
    "ExactOracleResult",
    "PruningStats",
    "abstract_p1_p2_counterexample",
    "evaluate_bound",
    "select_common_policy",
    "solve_dr_dual",
    "solve_exact",
    "solve_exact_two_ev_nonanticipative",
    "solve_info_gain_heuristic",
    "solve_passive_mpc",
    "solve_robust_mpc",
]
