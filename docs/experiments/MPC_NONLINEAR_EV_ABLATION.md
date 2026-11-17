# MPC nonlinear EV ablation (Campaign B)

- Protocol: `mpc_nonlinear_ev_ablation_v1`
- Plant: `nonlinear_piecewise_charge`; ablation planner: `linear_g_delta_soc_planning_only`
- Tight-EV: battery×0.25, keep 1 charger(s), partial recharge
- Cells: 8

## Physical near-full charge gap

- {'soc_from': 85.0, 'soc_to': 95.0, 'battery_capacity': 100.0, 'nonlinear_seconds': 15.621972632644553, 'linear_seconds': 10.0, 'linear_understates_by': 5.621972632644553, 'relative_understatement': 0.3598759750030904}

## Mechanism demo (Validate under linear vs nonlinear)

- mechanism_holds=True
- linear_ok=True nonlinear_ok=False
- charge times: linear=2.0, nonlinear=3.1243945265289104

## Closed-loop summary (honest; may be null if no charge acts)

- Nonlinear mean J: 46.65773837979308
- Linear-plan mean J: 46.65773837979308
- Mean ΔJ (NL−linear): 0.0
- Frac NL better J: 0.0
- Claim-support cells: 0 / 8
- Linear replay failures: 0
- Nonlinear replay failures: 0

## Claim scope

Local to predeclared tight-EV cells + physical near-full charge gap: nonlinear is necessary when linear planning understates charge time. Not a global J brag. Null closed-loop deltas are reported honestly when both planners emit the same acts.
