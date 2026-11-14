# Final oracle and certificate regressions

## Case-A restricted charging oracle (mandatory)

Reference causal values (shared plant scoring):

| Action | Expected value |
|--------|---------------:|
| Serve Near (B1-like) | 88.0 |
| Charge first | **≈122.29** |
| Δ | **≈+34.29** |

Live `CertificateCarryingEconomicMpc.decide()` on the Case-A observation, with the fork’s **restricted** action set `{serve_near, charge_first}` and the fork forecast scenarios:

- Selects **charge** (`v1 → S`)
- Commitment-feasible at decide time
- Subsequent physical episode **replay_ok**

**Honesty note.** With the *unrestricted* candidate generator, expected value prefers `wait_idle` (≈130.15) because deferring to B1 recourse can dominate committing to charge immediately. The mandatory paper oracle matches the published restricted comparison table; unrestricted preference for wait is recorded in `final_development_results.json`.

## Anti-always-charge

On the irreversible-admission fork without forecast pressure, CC-E-MPC selects service of `Now`, **not** charge. Pass.

## Certificate event regressions (`A_low_soc_charge`, seed 7)

Covered: announcement, mid-travel, mid-service, low SOC, timeout pressure, illegal new admission.

- Replay valid  
- Illegal re-accept of a completed customer rejected by validator  
- Certificates revalidated when present  

Charge mid-episode was not always observed on this case (battery/ops dependent); low-SOC and service paths are covered.
