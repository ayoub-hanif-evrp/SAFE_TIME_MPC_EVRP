# Gate 4 — Proof or Counterexample

## Hypothesis tested

EVRP resource structure admits a **sound, computationally useful, novel** bound on \(\Delta_r\) beyond known ADP / resource-extension methods.

## Candidate 1 — Insertion / displacement cost

**Idea:** bound \(\Delta_r\) by route insertion displacement + residual time.

**Result:** reduces to knapsack residual-time opportunity-cost proxies (Zhang et al., 2023). Produces only trivial sound intervals on the exact toy; no new dominance theorem.

**Verdict:** NO-GO for novelty.

## Candidate 2 — SOC / charger reachability

**Idea:** certify \(\Delta_r\) via residual battery and reachable charging.

**Result:** yields standard commitment **feasibility filters**, already present in robust EVRP certificates and ESPPRC resource extensions; proactive charging under stochastic requests treated by Jiang et al. (2026). No new structural compression of contingent admission value.

**Verdict:** NO-GO for novelty.

## Stop rule (executed)

Both candidates reduce to prior art without a new structural certificate → **stop theory investigation** for this contribution class.

## What remains scientifically useful

Platform validity repairs (offline labels, announcements, reactive baseline, timing, provenance) are preserved. A different MPC hypothesis is required for GO.
