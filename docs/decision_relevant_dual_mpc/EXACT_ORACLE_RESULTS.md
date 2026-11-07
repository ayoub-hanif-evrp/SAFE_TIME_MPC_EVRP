# Exact oracle scope and results

## Status label

`EXACT_OPTIMUM` means optimal within an **explicitly enumerated finite policy class**, not a continuous general EVRP optimum.

## Single-EV class

- First action: travel on one D→A corridor.
- Continuation family: serve A; optionally direct AC; optionally AS + full charge + SA + AC.
- Nonanticipative rule: if posterior support size > 1, one common plan for all remaining θ.

## Two-EV class (repaired)

Implemented in `fleet_oracle.py` (wired through `solve_exact("two")`):

1. EV1 chooses exploit/inform corridor; serves A1.
2. Global observation time `T_obs` = EV1 clock after travel; EV2 is waited to `T_obs` before using the posterior.
3. History key \(h=(\text{corridor}, \mathrm{supp}(b))\).
4. For each \(h\), EV2 selects **one** action in `{DIRECT, CHARGE, SKIP}` maximizing conditional expected reward; the same action applies to every θ mapping to \(h\).

**Nonanticipativity:** \(h_t(\theta_1)=h_t(\theta_2)\Rightarrow \pi(h_t(\theta_1))=\pi(h_t(\theta_2))\).

**Regression:** reverse ranking of DIRECT vs CHARGE across θ ⇒ common policy value = 5, clairvoyant per-θ max = 10 (must not report clairvoyant as exact).

## Known limitations

- Not integrated with the legacy event-driven `FleetSimulator` as the primary plant.
- Depot-return feasibility is **not** enforced by the limited continuation family.
- Dynamic request release is covered by semantics tests, not yet by the primary exact value table.
