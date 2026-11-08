# Physical contract — authoritative D-EVRP plant

**Status:** Phase B complete for plant selection and a verified closed-loop demo.

## Authoritative modules

| Role | Module |
|------|--------|
| Plant | `safe_time_evrp.environment.simulator.FleetSimulator` |
| Closed-loop driver (baseline MPC) | `safe_time_evrp.controllers.episode.run_episode` |
| Phase B demo driver | `safe_time_evrp.commitment_safe_mpc.phase_b_demo` |
| Independent replay | `safe_time_evrp.validation.replay.validate_log` |
| Facade | `safe_time_evrp.commitment_safe_mpc.plant` |

`dr_dual` atomic transitions remain an **oracle / dual-control sandbox**, not the fleet plant.

Reference engineering (adapt contracts only; do not merge trees): nearby `MPC_MCTS_Multi_agents_EVRP` (`evrp/simulator.py`, `observation.py`, `research_v3a/*`). The historical name “MPC_EVRP” in older notes maps to that sibling project when present.

## Mandatory semantics (implemented)

1. Multiple EVs with position, SOC, load, activity status  
2. Customer requests announced at scheduled release times (`schedule_release`)  
3. Request lifecycle: hidden → announced → accepted/deferred/rejected → in_service → completed / accepted_unfulfilled  
4. Hard customer time windows (checked at service start)  
5. Travel time and energy (nominal linear model; optional disturbance factors)  
6. Full charging (and partial when `charge_target` set)  
7. Noninterruptible travel / service / charge; interruptible window wait  
8. Depot return / terminal accounting in episode end  
9. One global chronological event heap (`self.time`)  
10. Replan triggers on observable events (`request_release`, `arrive`, `service_end`, `charge_end`, …)

## Information boundary

`Observation` has **no** hidden-future customer field. Controllers see only released/open, accepted, completed, rejected, in_service, deferred, and vehicle views (including locked destinations for noninterruptible actions).

Accepted commitments are distinct from provisional route suffixes on the `Decision`.

## Independent replay checks

`validate_log` recomputes, without trusting the optimizer:

- Global time order  
- Travel energy/timing and SOC  
- Load / payload  
- Service windows and duplicate service  
- Charging feasibility (including `charge_skip`)  
- Early access to unreleased requests  
- Interrupted travel  
- Accepted vs completed partitions  

## Phase B demonstration

Command:

```bash
python -m safe_time_evrp.commitment_safe_mpc.phase_b_demo
```

Artifact: `docs/commitment_safe_mpc/phase_b_demo.json`

Criteria met on the synthetic instance:

- two vehicles serve customers  
- dynamic releases (C3, C4 at t=50)  
- charging occurs  
- multiple replans  
- all accepted commitments completed  
- independent replay accepts the log  

The demo controller is a **plant-verification** policy with an explicit feasible charge plan, not the research ALNS baseline (Phase C).
