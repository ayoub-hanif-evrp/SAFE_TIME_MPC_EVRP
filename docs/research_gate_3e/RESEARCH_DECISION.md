# Gate 3E — Research decision

## Verdict: **REVISE**

## Checklist

| # | Question | Answer |
| ---: | --- | --- |
| 1 | Closed-loop experiment correct under stated plant model? | **Mostly yes** after P0 fixes (simulator, termination, strip+revalidate, commitment gate). Computation-time causality remains optional/off. |
| 2 | Can hidden future customers influence decisions? | **No** under anonymous forecasts + regression test. |
| 3 | Are all eligible requests processed and counted? | **Yes** — pending releases respected; announced/unannounced-at-cutoff recorded. |
| 4 | Does horizon change **executable** decisions? | **Yes** on the microscope (A service → S charge). |
| 5 | Do accepted promises remain feasible under claimed assumptions? | **Improved** — admission gate; solomon_140 RH trace shows 0 violations under 3E protocol. Not a robust-uncertainty certificate. |
| 6 | Paired experiments exactly reproducible? | **Yes** for seeds/manifest fields via SHA-256 (git commit recorded). |
| 7 | Stochastic predictive control outperform strong baseline? | **Not demonstrated** — no true stochastic policy-tree MPC in this gate. |
| 8 | Do battery/charging materially change decisions? | **Sometimes** — energy-active Amazon logs charges; microscope charge is horizon-causal. Flagship decisions often still service-identical across controllers. |
| 9 | Does flexibility terminal contribute beyond rollout? | **No** — sequences identical on the matched set. |
| 10 | Precise novelty hypothesis left? | **Yes, but not flexibility.** Candidate: irrevocable admission + charging under causal demand scenarios with commitment feasibility and compute limits — only if it beats established scenario lookahead/ADP with a clear algorithmic or decision-quality advantage. |

## Decision rule

- Harness/info/horizon/commitment contracts are in place → platform keepable.
- Flexibility terminal still equals deterministic prefix rollout → **retire flexibility as a novelty claim**.
- Do **not** start Part 3 automatically.
- Next work = one differentiated MPC mechanism **after** choosing a sharp hypothesis (Milestone 2), not more datasets.

## GO / REVISE / NO-GO

**REVISE:** scientific experiment trustworthiness is restored enough to stop using Gate 3D’s privileged-forecast results; the flexibility hypothesis remains negative; pursue a new mechanism only with a sharper claim than “another terminal penalty.”
