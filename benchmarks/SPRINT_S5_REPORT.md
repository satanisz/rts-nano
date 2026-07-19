# Sprint S5 Performance Report

Date: 2026-07-19
Reference: `benchmarks/BASELINE_CC100D6.md`

## Final standard benchmark

Three-sample medians using the original S0 command:

| Scenario | Metric | S0 baseline | S5 result |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 2.942 ms | 1.224 ms |
| Map 01 | Core throughput | 8,429 steps/s | 13,985 steps/s |
| Map 01 | Peak traced Python memory | 0.225 MiB | 0.236 MiB |
| Dispersed 400 | Two group orders | 2,634 ms | 1,561 ms |
| Dispersed 400 | Core throughput | 97.474 steps/s | 103.810 steps/s |
| Dispersed 400 | Peak traced Python memory | 0.984 MiB | 1.005 MiB |

The dispersed spatial-grid case remains more than seven times faster than the historical global-
scan result (about 14.5 steps/s), exceeding the required four-times advantage.

## Extended workloads

Three-sample medians, 200 ticks per scenario:

| Workload | Initialization | Commands | Throughput |
|---|---:|---:|---:|
| Idle map 01 | 1.027 ms | n/a | 15,522 steps/s |
| Active economy | 1.077 ms | 581.119 ms | 4,300 steps/s |
| Two-army combat (80 units) | 0.349 ms | 0.723 ms | 649 steps/s |
| 400 dispersed units | n/a | 1,742.031 ms | 83.517 steps/s |
| 400 close-combat units | 2.486 ms | 15.262 ms | 41.832 steps/s |

An idle 5,000-tick run retained 0.000 MiB of traced Python memory. Output events remain bounded to
one tick and presentation effects are not created headlessly.

## Profile findings and changes

Separate profiling covered creation, group assignment/pathfinding, movement/collisions, target
acquisition, spatial queries, and the observation-independent core tick.

- Twelve avoidable A* calls for formation slots inside building footprints dominated a 400-unit
  group command. Formation slots now reject building overlap before pathfinding.
- A* edge validation repeatedly allocated the same building list. One immutable building snapshot
  is now reused for each path search.
- Collision resolution received every entity in the much wider vision/acquisition query. Target
  acquisition and swept local collision queries are now separate; splash queries are centered on
  the actual target.
- Spatial updates are incremental after movement, spawn, construction, cancellation, and death,
  avoiding a second whole-world rebuild while keeping same-tick queries current.
- The simulation tick iterates one stable entity tuple and no longer creates repeated team and
  `all_entities` lists.

No flow field or shared path cache was added: after removing invalid formation slots, measurement
did not justify their complexity.

## Initial CI-safe budgets

These are review thresholds for comparable runners, not cross-machine guarantees:

| Metric | Budget |
|---|---:|
| Cold map 01 initialization | below 20 ms |
| Idle map 01 | at least 6,000 steps/s |
| Active economy | at least 2,500 steps/s |
| Two-army combat | at least 350 steps/s |
| 400 dispersed units | at least 60 steps/s |
| 400 close combat | at least 25 steps/s |
| Two dispersed group orders | below 5,000 ms |
| Idle retained memory after 5,000 ticks | at most 0.5 MiB |

Sprint S6 should initially report these metrics in CI. Enforcement should wait until runner
variance has been observed across multiple CI executions.

## Reproduction

```powershell
uv run python benchmarks/core_baseline.py --repeats 3 --map-steps 2000 --stress-steps 200
uv run python benchmarks/core_baseline.py --extended --repeats 3 --scenario-steps 200
```
