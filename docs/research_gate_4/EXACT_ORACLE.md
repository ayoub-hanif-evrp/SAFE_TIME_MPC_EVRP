# Gate 4 — Exact Commitment Oracle

## Scope

Tiny instance `gate4-commitment-toy`: 1 EV, 1 charger, customers \(A\) (accepted), \(R\) (admission decision), \(F\) (future, Bernoulli).

Module: `src/safe_time_evrp/mpc3c/commitment_oracle.py`

## Distinctions returned

| Quantity | Meaning |
|----------|---------|
| `v_without` | Expected completions if \(R\) rejected |
| `v_with` | Expected completions if \(R\) accepted (requires \(A,R\) jointly feasible) |
| `delta` | \(V(\mathcal A)-V(\mathcal A\cup\{R\})\) |
| `causal_accept` | Accept before knowing \(F\) |
| `clairvoyant_accept` | Whether some scenario prefers accept |
| `open_loop_accept` | Same single-epoch decision as causal here |

Status `EXACT` when enumeration completes; `UNKNOWN` if incomplete (not used on this toy).

## Command

```bash
python -c "from safe_time_evrp.mpc3c.commitment_oracle import exact_marginal_commitment_cost as e; print(e(p_future=0.5))"
python -c "from safe_time_evrp.mpc3c.commitment_oracle import investigate_commitment_cost_candidates as i; import json; print(json.dumps(i(), indent=2))"
```

## Role

The oracle establishes what exact marginal costs look like **before** proposing approximations. Phase C is blocked until a candidate bound differs from exact ADP/rollout decisions on such toys.
