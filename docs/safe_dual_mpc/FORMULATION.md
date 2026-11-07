# Formulation — Safe Dual MPC for Dynamic EV Delivery

## Energy model

Shared scalar latent factor \(\theta^\star\):
\[
e_{a,t}=\phi_0(a)+\phi_1(a)\,\theta^\star+\phi_\ell(a)\,\ell_t+\varepsilon_{a,t}.
\]

Features \(\phi\) are known proxies (base arc energy, informative probe coefficient). No fabricated slope/temperature observations. Vehicle-specific biases can be added later; the exact toy uses a fleet-shared \(\theta\).

Plant knows \(\theta^\star\); controllers never read it. Observations occur **only** after physical arc completion.

## Information state

Discrete belief \(b_t\) on a finite support (exact toy: \(\{0,1\}\)) or bounded-error set \(\Theta_t\) under \(|e-\phi^\top\theta|\le\bar\varepsilon\).

Also: SOC, payload, locked noninterruptible actions, accepted commitments \(\mathcal A\), announced requests, certified continuation if any.

## Safety contract (toy)

An action is admissible only if accepted customer \(A\) remains reachable under **every** \(\theta\) in the current support/set. Optional customers may be skipped. Charging is allowed but may destroy tight due feasibility.

## Dual objective (finite tree)

Maximize expected operational reward (completed deliveries minus mild energy cost) over causal policies, subject to the safety contract. Information value enters only through changes in future admissible decisions (charging / optional service), not as an entropy bonus.
