# Incremental proof sketch and counterexamples (repaired)

## Proposition

Under the deterministic nominal model, with exact forward resource profiles that
record per-visit states **and** tour freight manifests:

If anchors match, energy-model version matches, visits \(v_{1:k}\) are identical,
and manifests agree for all \(i \le k\), then

\[
\text{state after } k \text{ (candidate)} = \text{stored profile state after } k.
\]

Suffix feasibility from that state equals full evaluation from the anchor for the
complete candidate (same served set, distance, charge, depot return), because the
deterministic dynamics are Markov in the resource state.

## Counterexamples enforced in tests

1. Depot freight change (\(D{-}A{-}D\) vs \(D{-}A{-}B{-}D\)) → prefix length 0.  
2. Anchor SOC/time/onboard drift → prefix length 0.  
3. Onboard-only “coverage” without future service → validator rejects (`missing_commitments`).  
4. Locked travel toward A without service continuation → rejected.

## What remains standard prior art

Prefix/resource concatenation (Vidal et al.), fast ALNS move evaluation (Erdelić et al.),
EVRP labeling. The investigated MPC-specific piece is **event-aware certificate
advancement** across replans under irreversible commitments — still compared honestly
in `SCIENTIFIC_VERDICT.md`.
