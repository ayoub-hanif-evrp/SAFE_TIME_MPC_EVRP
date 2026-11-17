# MPC paper evaluation (multi-dataset)

**Protocol:** `mpc_paper_multi_dataset_v1`

## Controller names (paper)

- `css_spi` → **Proposed: commitment-safe stochastic MPC (SPI)**
- `css_spi_forecast` → **Ablation: proposed + demand forecast**
- `css_spi_off` → **Ablation: proposed without SPI (legacy ranked selection)**
- `cce_greedy_nominal` → **Economic MPC — greedy nominal scoring**
- `full_validation_alns_mpc` → **Full-validation ALNS–MPC**
- `certificate_carrying_alns_mpc` → **Certificate-carrying ALNS–MPC**
- `stochastic_cce_causal` → **Scenario economic MPC (sampled futures)**

## Dataset roles

- **Schneider E-VRPTW** — primary economic table (development; test sealed)
- **EVRP-TW-D** — confirmatory geography (frozen Cus_5 / Cus_15 subset)
- **Homberger + chargers** — latency appendix only (separate file)

## Schneider gate: PASS

Mean ΔJ ≥ 0 with tally better≥worse and no AU increase (mean=375.9980996905022, tally={'better': 9, 'worse': 0, 'tie': 0}, AU mean=-1.2777777777777777, AU ci={'level': 0.95, 'method': 'stem_clustered_paired_t', 'df': 8, 'se': 0.6724288020505669, 'low': -2.8283985953063846, 'high': 0.27284303975082946}).

- Compute p50=0.11880010005552322, p99=1.319133899989538

### Paired deltas (proposed − baseline)

- Proposed: commitment-safe stochastic MPC (SPI) − Economic MPC — greedy nominal scoring: mean=375.9980996905022, CI=[-59.913826714728884, 811.9100260957333], tally={'better': 9, 'worse': 0, 'tie': 0}
- Proposed: commitment-safe stochastic MPC (SPI) − Economic MPC — greedy nominal scoring: mean=-1.2777777777777777, CI=[-2.8283985953063846, 0.27284303975082946], tally={'better': 0, 'worse': 4, 'tie': 5}
- Proposed: commitment-safe stochastic MPC (SPI) − Full-validation ALNS–MPC: mean=146.48875577480854, CI=[-328.7664027631014, 621.7439143127185], tally={'better': 8, 'worse': 1, 'tie': 0}
- Proposed: commitment-safe stochastic MPC (SPI) − Certificate-carrying ALNS–MPC: mean=231.72318919768057, CI=[40.46551405586544, 422.9808643394957], tally={'better': 9, 'worse': 0, 'tie': 0}
- Proposed: commitment-safe stochastic MPC (SPI) − Scenario economic MPC (sampled futures): mean=-95.90449677861143, CI=[-248.59867066274, 56.78967710551716], tally={'better': 3, 'worse': 6, 'tie': 0}
- Proposed: commitment-safe stochastic MPC (SPI) − Ablation: proposed + demand forecast: mean=94.29527814211421, CI=[-55.97148541897663, 244.56204170320507], tally={'better': 5, 'worse': 4, 'tie': 0}
- Proposed: commitment-safe stochastic MPC (SPI) − Ablation: proposed without SPI (legacy ranked selection): mean=214.9122725080718, CI=[-90.22838293851498, 520.0529279546586], tally={'better': 8, 'worse': 1, 'tie': 0}

## EVRP-TW-D confirmatory

- Frozen stems: Cus_5/solomon_dataset_0_RC_narrow_1769114883, Cus_5/solomon_dataset_190_RC_wide_1769114883, Cus_5/solomon_dataset_325_C_wide_1769114883, Cus_5/solomon_dataset_550_R_wide_1769114883, Cus_15/solomon_dataset_0_RC_wide_1769114904, Cus_15/solomon_dataset_190_RC_wide_1769114904, Cus_15/solomon_dataset_325_R_narrow_1769114904, Cus_15/solomon_dataset_550_RC_wide_1769114904
- Note: Full Cus_5/Cus_15 archives have 1000 files each; this freeze is predeclared for wall-time. Not pooled with Schneider for average J.

- Proposed: commitment-safe stochastic MPC (SPI) − Economic MPC — greedy nominal scoring: mean=7.039200498561707, CI=[-11.50991773145543, 25.58831872857884], tally={'better': 3, 'worse': 1, 'tie': 4}
- Proposed: commitment-safe stochastic MPC (SPI) − Full-validation ALNS–MPC: mean=104.50080624614397, CI=[54.03950833207799, 154.96210416020995], tally={'better': 8, 'worse': 0, 'tie': 0}
- Proposed: commitment-safe stochastic MPC (SPI) − Certificate-carrying ALNS–MPC: mean=104.50080624614397, CI=[54.03950833207799, 154.96210416020995], tally={'better': 8, 'worse': 0, 'tie': 0}
- Proposed: commitment-safe stochastic MPC (SPI) − Scenario economic MPC (sampled futures): mean=40.430257418417696, CI=[-12.071701435792711, 92.9322162726281], tally={'better': 5, 'worse': 1, 'tie': 2}

## Nonlinear charging ablation

- See `MPC_NONLINEAR_EV_ABLATION.md` (mechanism_holds=True)

## Homberger latency

- See `MPC_HOMBERGER_LATENCY.md`
- Proposed decide p50≈1.05s; greedy-nominal p50≈1.39s (timed decide on large instances; appendix only).
