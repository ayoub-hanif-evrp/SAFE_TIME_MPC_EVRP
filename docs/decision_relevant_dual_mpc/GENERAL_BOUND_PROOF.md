# Generic resource bounds — proof status

Implementation: `dr_dual/generic/general_bound.py`  
Status API: `VALID_BOUND` | `UNSUPPORTED_BOUND` | `PROVEN_INFEASIBLE` | `UNKNOWN`

**Current research status:** the prior generic TEI construction is **QUARANTINED**. It must not prune candidates on the wider dynamic-request model.

## Counterexample (invalidates prior claim)

On `make_tiny_generic_instance(n_customers=3)` after first travel `D_N0_exploit`, a feasible continuation serving later-announced cust_1 yields \(\mathbb E[R]\approx 14.625\).

The legacy TEI pending set (post-travel announced/accepted only) produced \(\overline Q_{\mathrm{legacy}}=9.85 < 14.625\).

Therefore the previous proposition “`VALID_BOUND` ⇒ \(Q^\star(a)\le \overline Q_{\mathrm{gen}}(a)\)” is **false** for the dynamic announcement model.

Reproduction: `counterexamples.old_bound_undercounts_future_announcement`  
Public API: `evaluate_generic_resource_bound` → `UNSUPPORTED_BOUND` (`QUARANTINED_...`).  
Unsafe code path kept as `evaluate_generic_resource_bound_legacy_unsafe` for tests only.

## Temporary certified baseline — trivial safe reward UB

\[
\overline Q_{\mathrm{triv}}(a)=\mathbb E_\theta\big[r_{\mathrm{travel}}(a,\theta)\big]+\sum_{c\in\mathcal E(H)}\mathrm{reward}_c
\]

where \(\mathcal E(H)\) is the set of customers whose release time is ≤ declared horizon \(H\) (or already accepted), excluding completed, and future energy/time costs are ignored (nonnegative ⇒ optimistic).

**Proposition.** For the same objective, demand releases, and horizon as the oracle, \(Q^\star(a)\le \overline Q_{\mathrm{triv}}(a)\) whenever the bound returns `VALID_BOUND`.

**Proof.** Any feasible policy collects at most one service reward per eligible customer and pays nonnegative future energy costs. The travel term matches the oracle’s first-action reward. Hence the envelope dominates.

API: `evaluate_trivial_safe_reward_bound` (used by solver `bound_mode=generic`).

## Prior TEI construction (historical; not certified)

For first travel \(a\), the old formula summed rewards of customers optimistically reachable from the post-travel node under min energy/time over the posterior support, with ≤1 full charge. Defects vs dynamic EVRP:

1. Pending set omitted future announcements inside the horizon.
2. One-charge relaxation understates multi-stop charging needs for reachability certificates.
3. State-search cutoffs could be misread as unreachability.
4. Fleet commitments were checked from the acting vehicle only.

None of (2)–(4) are compatible with a general infeasibility certificate unless the policy class is restricted accordingly — and (1) alone already falsifies validity.

## What remains to rebuild (P2 — after oracle is trusted)

A repaired general UB must include:

- All legally eligible future customer rewards under the declared horizon
- Optimistic fleet-wide time–energy reachability (or unlimited-charging relaxation)
- Observation timing / nonanticipativity
- Accepted commitments over the **fleet**
- Proof \(Q^\star(a)\le Q_{\mathrm{upper}}(a)\) on the **same** finite-state control problem as the oracle

Falsification rule unchanged: any `VALID_BOUND` strictly below exact \(Q^\star\) invalidates certified pruning.
