# Exact oracle results

## Scope label

`EXACT_OPTIMUM` means optimal in the enumerated finite policy tree:
first travel among named corridors + continuation family
{stop after A, A→C, A→S charge_full →A→C}.

Not a continuous general EVRP optimum.

## Single-EV corridors (`dr_single_ev_corridors`)

| Policy | First action | Value |
|--------|--------------|------:|
| Exact safe dual | `DA_inform` | 12.125 |
| Optimized passive (ignore posterior in scoring) | `DA_exploit` (differs) | lower robust score |
| Clairvoyant | θ-dependent | ≥ dual |

Commands:

```bash
python -c "from safe_time_evrp.dr_dual.exact_oracle import solve_exact; print(solve_exact('single'))"
python -m pytest -q tests/test_dr_dual.py
```

## Two-EV shared θ

Oracle runs (`solve_exact('two')`). On the current timing/energy calibration, the reported best first action is **not** yet a clean cross-vehicle inform win (`cross_vehicle=false` in artifacts). Documented as **open instance-tuning item**, not as a demonstrated fleet VoI theorem.
