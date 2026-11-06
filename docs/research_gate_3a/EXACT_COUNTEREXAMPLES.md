# Exact counterexamples (Gate B)

All claims are checked by `tests/test_gate3a_multistage.py` against the independent
oracle in `src/safe_time_evrp/multistage/` (not `robust/certificate.py`).

## CEX-1: Routing fork (`routing_fork_commitment`)

**Claim.** There exists a tiny discrete instance where:

| Mode | Status |
| --- | --- |
| Open-loop | PROVEN_INFEASIBLE |
| Two-stage fixed-route + adjustable charge (Han-style) | PROVEN_INFEASIBLE |
| Causal multistage feedback | PROVEN_FEASIBLE |
| Clairvoyant | PROVEN_FEASIBLE |

**Mechanism.** After `D→J`, the plant reveals `(time, SOC)`:

- Low/slow arrival: high SOC, late clock → must take direct `J→C` (detour misses due).
- High/fast arrival: low SOC, early clock → must take `J→S→C` with a unit charge (direct lacks energy).

No single fixed travel sequence covers both worlds, so Han-style adjustable charge on a
fixed first-stage route cannot recover the feedback outcome. This is the Gate B gap versus
Han on the **routing** axis (not merely charge recourse).

## CEX-2: Residual-budget reset harm (`budget_reset_sensitive`)

**Claim.**

| Mode | Status |
| --- | --- |
| Feedback with correct residual \(\Gamma_{\mathrm{rem}}\) | PROVEN_INFEASIBLE |
| Feedback with illegal full \(\Gamma\) reset after each arc | PROVEN_FEASIBLE |

Both mandatory arcs spend \(z=1\) with \(\Gamma=1\). Resetting the budget manufactures a
false feasible certificate. Controllers must carry residual budget in the information state.

## Negative control N1: Feedback useless (`feedback_useless`)

Open-loop, two-stage, and feedback are all PROVEN_FEASIBLE. Feedback adds no feasibility
value. Guards against claiming multistage gains on every toy.

## Negative control N2: Two-stage charge sufficient (`two_stage_charge_sufficient`)

| Mode | Status |
| --- | --- |
| Open-loop (fixed charge) | PROVEN_INFEASIBLE |
| Two-stage fixed-route + adjustable charge | PROVEN_FEASIBLE |
| Feedback | PROVEN_FEASIBLE |

When the only recourse needed is wait-and-see charging on a fixed sequence, Han-style
two-stage already matches feedback. Adaptive charge alone is **not** a novelty claim.

## Nonanticipativity

Renaming arc modes without changing `(time, energy, z)` leaves feedback status unchanged
(`test_nonanticipativity_feedback_ignores_future_mode_labels`). Policies depend only on
observed state, not on unrealized future labels.

## Implication for Gate C

CEX-1 leaves a literature gap relative to fixed-route Han. Gate C must still produce a
sound **EVRP-specific** terminal-viability rule cheaper than policy-tree / Bellman
enumeration. If the only sound certificate is the feedback DP itself, treat as known-result
collapse.
