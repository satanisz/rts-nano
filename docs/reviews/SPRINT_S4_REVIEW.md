# Sprint S4 Review — Pure Simulation and Thin Pygame Application

Date: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`
Verdict: **APPROVED**

## Scope reviewed

- pure rectangle geometry with former SDL/Pygame clipping semantics,
- terrain collision data separated from procedural Pygame rendering,
- `SimulationRunner` owning tick order, ticks, systems, and bounded output events,
- application-owned camera, viewport, menu, pause, current team, and selection,
- presentation-owned command panel, click markers, fog refresh, projectiles, and effects,
- replacement of `game/manager.py` by `application/GameSession`,
- headless startup without Pygame import or SDL environment mutation.

## Correctness findings

The geometry migration preserves inclusive left/top and exclusive right/bottom edges, inflation,
point collision, and integer Cohen-Sutherland line clipping. Representative results were compared
against Pygame/SDL before being encoded as pure geometry tests. Terrain transition, water, rock,
ramp, and replay behavior remain unchanged.

`SimulationRunner.step()` owns the gameplay order: terrain heights, spatial rebuild, unit updates,
gathering, construction, production, towers, effects, death removal, and victory. `GameSession`
only applies application pause and removes dead objects from selection. `GameState` no longer owns
current-team, pause, or selection state, and simulation entities no longer own selection flags.

The S0 golden digest remains:

```text
239c2b1b85c30a2d07526157f622dc297f844b04ed5ce2b63b692e02138f5c90
```

## Architecture findings

The direct-Pygame core debt allowlist is empty. `PresentationState` shares command-panel and click-
marker state between input and rendering. Projectile lifetimes, terrain drawing, fog refresh,
fonts, surfaces, and image caches are presentation-only.

There is no `GameManager` compatibility module. Fresh-process checks prove imports of simulation
entities, terrain, application composition, and headless helpers do not load Pygame. Headless also
does not configure SDL environment variables.

## Quality gate

| Check | Result |
|---|---|
| Ruff check / format | Passed |
| Ty | Passed |
| Pytest | 171 passed |
| Coverage | 71.72% (50% requirement passed) |
| All shipped maps | Passed |
| Deterministic replay | Passed; digest unchanged |
| Fresh-process headless import | Passed; no Pygame or SDL mutation |
| Render/simulation parity | Passed |
| Every-content render smoke | Passed |
| Headless benchmark smoke | Passed |
| `git diff --check` | Passed |

## Performance review

The final three-sample S4 smoke medians reported:

- map 01 cold initialization: 1.117 ms,
- map 01 throughput: 8,153 steps/s over 500 ticks,
- 400-unit group orders: 2,535 ms,
- 400-unit throughput: 96.381 steps/s over 50 ticks,
- peak traced Python memory: 0.236 MiB for map 01 and 1.002 MiB for stress.

Results remain consistent with S3 and S0. The bounded event queue is cleared every step whether or
not presentation exists; headless retains no projectile or marker objects.

## Safety review

- S4 was split into geometry, terrain-presentation, and runner/session commits with a full gate
  after each reviewable change.
- Existing user artwork and temporary files remain unstaged.
- No gameplay value, balance, AI behavior, reward, RL integration, or map content changed.
- Existing headless operations continue to pass their regression suite.

## Decision

Sprint S4 meets its exit criteria and is approved for its final runner/session commit. Sprint S5
may begin after that commit is created successfully.
