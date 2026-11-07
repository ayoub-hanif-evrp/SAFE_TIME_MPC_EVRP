# Correction audit (post-`93fd812`)

## Prior tip (`93fd812`) — what was already fixed

- Removed illegal `min_θ max_π` incumbent L.
- Common continuation policy for ambiguous beliefs.
- Withdrew unsound zero-VoI certificate.
- Commitment completion / busy / payload checks.
- Compute counters beyond first-action expansions.

## Remaining defects addressed in this wave

| ID | Defect | Repair |
|----|--------|--------|
| P0 | Two-EV oracle θ-dependent EV2 choice | History-indexed policy + `T_obs` sync (`fleet_oracle.py`) |
| P0 | REUB not a general UB (misses charge-then-C) | Counterexample invalidates v0; REUB_v1 + family proposition; no clairvoyant fallback certification |
| P0 | Robust baseline used Bayesian valuation | `solve_robust_mpc` / `solve_passive_mpc` with forced-prior scores |
| P1 | Unpruned still computed bounds | `use_pruning=False` skips all UB evaluations |
| P1 | Semantics / info cases | Validation tests: announce/accept, replay, 3 EV-info cases |

## Honest residual gaps

- REUB_v1 is family-restricted and often looser than DRUB → not yet a strong algorithmic contribution.
- Toy compute deltas remain small/noisy.
- No large-benchmark evidence.

## Separation of contribution

| Component | Status |
|-----------|--------|
| Perfect-information / clairvoyant UB pruning | Established algorithm (not novelty) |
| Nonanticipative dual first-action oracle (tiny) | Corrected prototype |
| REUB_v1 charge envelope | Provisional family result; needs stronger general theory |
| Decision-relevant pruning advantage at scale | **Not established** |
