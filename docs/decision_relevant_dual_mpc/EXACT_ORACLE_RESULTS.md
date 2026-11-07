# Exact oracle scope and results

## Status label

`EXACT_OPTIMUM` means optimal within an **explicitly enumerated finite policy class**.

## Single-EV

First D→A corridor + continuation family {stop after A, direct AC, AS+charge+SA+AC}. Ambiguous posterior ⇒ one common plan.

## Two-EV (nonanticipative)

`fleet_oracle.py`: history-indexed EV2 policy; sync to \(T_{\mathrm{obs}}\).

### Fleet VoI (critical)

- **Legacy network:** \(\Delta\) VoI = 0 under controlled share/no-share (charge weakly dominates).
- **Positive-VoI network:** \(\Delta\) VoI > 0 with tight battery and costly charge detour.

Do not claim cross-vehicle benefit from contingent labels alone.

## Limitations

- Default continuation family does not require depot return.
- Announcement lifecycle demonstrated in `generic_small.py`, not fully folded into every exact table row.
- Independent replay: `replay.py` (recomputes from PlantLog without `apply_action`).
