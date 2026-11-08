# Scientific verdict

**Current:** Request-rescue B0, hardened B1, and M1 (incremental eval + event certificates) are implemented with development evidence.  
**Paper claim:** **NOT YET** — no demonstrated large-scale MPC advantage; incremental resource reuse is largely standard prior art; EVRP-MPC-specific theorem not established beyond exact-prefix agreement tests.

### Final scientific questions

1. **Can ALNS recover constructor-excluded requests?** Yes — packing fixture: constructor `{A,B}`, ALNS/B1/M1 recover `{A,B,C}` (`test_commitment_safe_rescue.py`, `ALNS_REQUEST_RESCUE.md`).  
2. **Does B1 enforce the declared contract?** Yes for locked empty-suffix, station-capacity refusal, accept-after-validate, no official-reject resurrection; nominal physics only.  
3. **Runtime fraction in candidate evaluation vs final validation?** Candidate `evaluate_route` dominates; B1 validation fraction is small on toys (`compute_bottleneck_profile.json`).  
4. **Incremental ≡ full on supported cases?** Required by regression tests for feasibility/served/distance on supported edits; uncertain cases fall back to full.  
5. **What theorem is established?** Exact-prefix resource agreement sketch + code equivalence tests — not a new complexity theorem.  
6. **How much compute does M1 save?** See ablation JSON; do not claim large savings from toys alone.  
7. **Does saving improve service at fixed budget?** Development suite: rescue improves coverage vs constructor; M1 vs B1 service often tied on tiny cases — no automatic quality win.  
8. **Robust across instances?** Not established beyond development/scaled synthetics.  
9. **Prior art?** Vidal timing/concatenation; Erdelić fast EVRP-ALNS; Sivagnanam prompt confirmation; EVRP time/SOC labeling — prefix reuse and anytime routing are standard. Distinctive target remains event-aware commitment invalidation under electric constraints, still unproven as novelty.  
10. **Ready for large EVRP benchmarks / paper?** Infrastructure yes; scientific claim no.

### Prior art (targeted)

- Vidal et al. 2015, Networks DOI 10.1002/net.21587  
- Erdelić et al. 2026, CIE DOI 10.1016/j.cie.2025.111758  
- Sivagnanam et al. 2026, arXiv 2603.07422  
- EVRP BPC labeling DOI 10.1287/trsc.2024.0725  
