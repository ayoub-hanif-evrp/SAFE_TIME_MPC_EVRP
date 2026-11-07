# Experimental evidence (development, tiny)

## Commands

```bash
python -m ruff format --check .
python -m ruff check .
python -m pytest -q tests/test_safe_dual_mpc.py tests/test_gate4_validity.py
python -c "from safe_time_evrp.dual_mpc.exact_oracle import run_exact_dual_example as r; print(r())"
python -c "from safe_time_evrp.dual_mpc.controllers import matched_comparison as m; import json; print(json.dumps(m(), indent=2))"
```

## Matched dual vs passive (both true \(\theta\))

| Metric | Safe passive | Safe dual |
|--------|--------------|-----------|
| Mean reward | 9.6 | 12.05 |
| Fraction serving optional C | 0.0 | 0.5 |
| First action | exploit | inform |

Initial beliefs, hidden \(\theta\) grid, commitments, horizons, and observation rules are matched. Clairvoyant is privileged upper reference only.

## What was **not** run

- No large Part 3 / EVRP-TW-D campaign for dual MPC.
- No claim that the toy transfers to Amazon/ESOGU at scale.
- Gate 4 result frozen: mean RH−reactive = 0 on 24 exploratory rows (unrelated to dual energy learning).
