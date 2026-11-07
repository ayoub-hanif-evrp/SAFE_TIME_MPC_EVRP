# Proof status and limitations

## Proved (conditional, tiny model)

On `DualToyParams` with zero noise and finite \(\theta\)-support:

1. Both EXPLOIT and INFORM are commitment-safe for A under \(\Theta_0=\{0,1\}\).
2. Safe passive’s Bayes value equals 9.6; safe dual’s equals 12.05.
3. The unique safe Bayes-optimal first action is INFORM.
4. Therefore information value changes the executable first action versus safe passive learning.

Proof method: exhaustive evaluation of the finite policy tree (code = certificate for this model).

## Not proved

- No new dominance rule for ESPPRC / resource labels.
- No complexity reduction theorem for dual EVRP policy trees.
- No recursive feasibility for arbitrary future demand or unbounded disturbances.
- No regret bound competing with Åkerblom.
- No guarantee that the toy gap survives realistic multi-customer Euclidean EVRP-TW-D geometry.

## Mechanism honesty

Implemented rule:
\[
a_t\in\arg\max_{a\in\mathcal U(\Theta_t)}\mathbb E[V\mid \text{posterior after }a]
\]
with \(\mathcal U(\Theta_t)=\) actions retaining a commitment continuation under all \(\theta\in\Theta_t\).

This **reduces to known constrained dual control / safe learning-MPC**. The EVRP packaging is a formulation contribution; it is not yet a new theorem.
