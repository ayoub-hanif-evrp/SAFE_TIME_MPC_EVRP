# Exact dual-control example (independently verified)

## Scope of exactness

**EXACT** inside the finite decision tree of `DualToyParams` (2 first actions × Bayesian posterior continuations × \(\theta\in\{0,1\}\)).  
Not a continuous-space global EVRP optimum. Truncation returns `UNKNOWN` (not used here).

## Story

- Accepted commitment **A** must remain feasible under all prior \(\theta\).
- Optional customer **C** has a tight due: charging after A makes C late.
- **EXPLOIT** corridor: energy \(4\) independent of \(\theta\) → no learning; SOC after A = 8.
- **INFORM** corridor: energy \(3+3\theta\) → observation reveals \(\theta\); slightly slower.
- Arc A→C energy \(6+3\theta\): needs SOC ≥ 6 if \(\theta=0\), ≥ 9 if \(\theta=1\).

## Results

| Policy | First action | Expected reward |
|--------|--------------|-----------------|
| Clairvoyant | best given \(\theta\) | 12.15 |
| Certainty-equivalent | EXPLOIT | (unsafe CE score) |
| Safe passive learning | EXPLOIT | **9.6** (never serves C: residual ambiguity forces skip) |
| Safe dual / exact Bayes-adaptive | **INFORM** | **12.05** (serves C iff \(\theta=0\)) |

Independent manual check matches the oracle (`verify_phenomenon_independent`).

## Why this is EV-specific (on the toy)

The value of information is the option to **skip charging** and still serve C under low \(\theta\), which couples battery residual, charger dwell time, and a delivery due date under an irrevocable A commitment. A pure navigation bandit without TW/charge would not encode this fork.
