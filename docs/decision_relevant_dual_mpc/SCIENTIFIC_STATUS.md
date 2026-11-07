# Scientific status

**Branch:** `research/decision-relevant-dual-mpc`  
**Advance tip:** post-`c81c773` (fleet VoI isolation, OTUB, preregistered suite)

## Verdict: **NOT YET SUBSTANTIVE**

The method is mathematically improving and experimentally cleaner, but it does **not** yet deliver a differentiated, computationally useful algorithmic contribution suitable for a top-tier EVRP–MPC claim.

### Precise answers

1. **Cross-vehicle information value?** On the legacy two-EV toy: **ΔVoI = 0** (charge weakly dominates; sharing changes labels, not value). On a redesigned tight-battery network: **ΔVoI > 0** (strict). Legacy “adaptive routes” were not economic value.
2. **New bound valid?** OTUB: **yes, family-restricted** (`UNSUPPORTED_BOUND` outside `{A,C,S}`). REUB_v1: family-restricted (v0 invalid).
3. **Respects observation timing?** OTUB: **yes** (common pattern on ambiguous information sets; contingent only after separation).
4. **Substantially cheaper than exhaustive continuation?** **Not demonstrated** — suite shows 0/8 instances with fewer total heavy ops under pruning.
5. **Prunes more than generic cheap bounds?** Unclear / not established as a win; REUB/OTUB prune decoys but overhead dominates.
6. **Retains exact decisions on independent small instances?** **Yes** (8/8 suite) for DRUB, REUB_v1, OTUB.
7. **Useful with charging & announcements?** Charging encoded; announcement demo exists; not yet a primary exact multi-request campaign.
8. **New math beyond generic info-relaxation / B&B?** **No** — OTUB is a structured family bound with classical nonanticipativity ideas; not a general EVRP theorem.

### What counts as success next (unchanged)

A reusable proved bound whose **total** computation (including bound build) beats unpruned search on varied instances, with a clear timing–commitment mechanism — then connect to the event-driven simulator / EVRP-TW-D.

### Commands

```bash
python -m pytest -q tests/test_dr_dual.py tests/test_dr_dual_repair.py tests/test_dr_dual_validation.py tests/test_dr_dual_advance.py
python -m safe_time_evrp.dr_dual.compute_study
python -c "from safe_time_evrp.dr_dual.experiments import write_artifacts; from pathlib import Path; write_artifacts(Path('docs/decision_relevant_dual_mpc'))"
```
