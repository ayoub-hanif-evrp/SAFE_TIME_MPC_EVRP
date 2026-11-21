# Hanif / Homberger A+B latency results

**Protocol:** `mpc_hanif_latency_ab_v1`
**Wall hours:** 0.306
**Workers:** 8

## Primary (cap=25, all A+B)
- n_cells: 120
- Proposed: {'n_cells': 120, 'n_hard_fails': 0, 'latency': {'n': 600, 'mean': 2.3629709311675593, 'median': 2.234661300026346, 'p50': 2.234027500031516, 'p90': 3.3020804999396205, 'p99': 4.121486499905586, 'max': 4.43579950009007, 'frac_over_budget': 0.6616666666666666}, 'p50_under_budget': False}
- GN: {'n_cells': 120, 'n_hard_fails': 0, 'latency': {'n': 600, 'mean': 3.0621367723316264, 'median': 2.763277499936521, 'p50': 2.7618689999217167, 'p90': 4.334245000034571, 'p99': 6.0210699000163, 'max': 7.159125300007872, 'frac_over_budget': 1.0}, 'p50_under_budget': False}
- Pass (0 hard fails + proposed p50≤2.0): **False**

### By variant
- **A:** proposed p50=2.227828499977477 fails=0
- **B:** proposed p50=2.2465520000550896 fails=0

## Cap curve (stratified 12 files)

- cap=25: proposed p50=2.1283228000393137, hard_fails=0
- cap=50: proposed p50=2.4816546998918056, hard_fails=0
- cap=100: proposed p50=3.5988364999648184, hard_fails=0
- cap=200: proposed p50=5.680134399910457, hard_fails=0
