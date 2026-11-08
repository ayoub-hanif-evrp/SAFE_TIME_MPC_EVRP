# Incremental route-resource certificates (repaired)

Module: `route_resource_profile.py`

## Freight-manifest prefix theorem (nominal)

Under deterministic nominal linear energy, identical vehicle anchors, and identical
**depot/reload freight manifests**, if a candidate shares visits \(v_{1:k}\) with a
validated profile **and** the active tour manifest at each index \(i \le k\) matches,
then the resource state after position \(k\) equals the stored profile state.

**Counterexample (invalid reuse):** \(D \to A \to D\) vs \(D \to A \to B \to D\) share
visit \(A\), but depot manifests \(\{A\}\) vs \(\{A,B\}\) differ, so reusable prefix is 0.

## Modes

| Mode | Hot path |
|------|----------|
| `FULL_EVALUATION` | `evaluate_route` from anchor |
| `INCREMENTAL_EVALUATION` | Recover exact prefix state; **`propagate_from_state` on suffix only** — no full `evaluate_route` on the candidate |

Uncertain / mismatched manifests → recompute from anchor via `propagate_from_state` (still not a silent approximate certify).

## Work counters

`prefix_visits_reused`, `suffix_visits_recomputed`, `full_calls_avoided`, `evaluate_route_calls`, propagate/profile seconds.
