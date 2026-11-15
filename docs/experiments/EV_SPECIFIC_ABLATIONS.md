# EV-specific ablations (Stage 4 — protocol only)

Predeclared factors (do not peek at confirmatory results while designing):

| Factor | Levels |
| --- | --- |
| Battery scarcity | nominal / tight (scaled capacity) |
| Charger availability | full Schneider set / subset |
| Fleet size | protocol v2 rule / −1 vehicle |
| Windows | as-is / tightened dues |
| Arrival pressure | low / medium / high dynamicity |
| Charge travel cost | nominal / inflated charger detours |

**Required mechanism test:** infinite/relaxed battery ablation. If predictive gains
persist unchanged when EV constraints vanish, the electric-specific claim fails.

**Data honesty:** Schneider-derived EVRPTW is the controlled plant. LaDe/Amazon
may supply request timing only — never label modeled SoC as measured EV telemetry.

**Status:** Protocol frozen; experiments **not** run (Stage 6 blocked).
