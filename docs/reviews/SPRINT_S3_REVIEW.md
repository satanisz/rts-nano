# Sprint S3 Review — Pure Simulation Entities

Date: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`
Verdict: **APPROVED**

## Scope reviewed

- entity models moved from `game/assets/entities/` to `simulation/entities/`,
- removal of Pygame, surfaces, images, portraits, draw methods, asset paths, and file I/O from
  entity construction,
- presentation-owned sprite, portrait, fitted-surface, and flipped-sprite caches,
- presentation-owned building placeholders, unit facing, hit flash timing, and projectiles,
- bounded pure `AttackLanded` outputs emitted only when a presentation adapter is attached,
- removal of `load_visuals` and `visual_assets_enabled` from the core API,
- rendering parity and fresh-process import protection.

## Correctness findings

Entity models contain deterministic gameplay state and behavior only. A fresh process can import
`rts_nano.simulation.entities` without loading Pygame. Constructors do no presentation work and
have no `image`, `original_image`, or `avatar_image` fields.

The renderer resolves assets from `visual_key`, category, and team. Missing files return a
presentation fallback without changing simulation state. Normal, fitted, portrait, and flipped
surfaces are cached in `PygameAssets`, never on an entity. Facing and attack flash expiry are
renderer-owned. Cosmetic projectiles consume already-resolved `AttackLanded` events and cannot
apply damage.

A comparative test executes identical commands in two simulations while drawing only one of
them after every tick. Their complete serializable snapshots remain equal. The S0 golden replay
also remains unchanged:

```text
239c2b1b85c30a2d07526157f622dc297f844b04ed5ce2b63b692e02138f5c90
```

## Architecture findings

The direct-Pygame debt allowlist shrank from three modules to two: `game/manager.py` and
`game/terrain.py`. Those modules remain explicit S4 work. The simulation entity package has no
compatibility facade at its former path; all application, game-system, test, and benchmark imports
use the new package directly.

Presentation event generation is disabled unless a renderer attaches. This preserves headless
performance and prevents an unrendered match from retaining or advancing visual objects. Only the
current tick's immutable attack outputs are retained by the manager; projectile lifetime belongs
to the renderer.

## Quality gate

| Check | Result |
|---|---|
| Ruff check | Passed |
| Ruff format check | Passed, 73 files unchanged |
| Ty | Passed |
| Pytest | 162 passed |
| Coverage | 70.67% (50% requirement passed) |
| Map 01 validation | Passed |
| Map 02 validation | Passed |
| Map 03 validation | Passed |
| Deterministic replay | Passed; digest unchanged |
| Fresh-process entity import | Passed; Pygame absent |
| Render/simulation parity | Passed |
| Every-content render smoke | Passed |
| Headless benchmark smoke | Passed |
| `git diff --check` | Passed |

## Performance review

The final three-sample S3 smoke medians reported:

- map 01 cold initialization: 1.034 ms,
- map 01 core throughput: 8,580 steps/s over 500 ticks,
- 400-unit group orders: 2,484 ms,
- 400-unit throughput: 96.930 steps/s over 50 ticks,
- peak traced Python memory: 0.239 MiB for map 01 and 1.002 MiB for stress.

S2 reported 3.041 ms, 8,789 steps/s, 2,490 ms, and 96.261 steps/s for the same smoke shape.
Removing entity asset I/O materially improves cold initialization while tick and stress results
remain within normal local variance. An explicit parent-commit comparison was also run after a
noisy long sample; it confirmed that pathfinding and collision work dominate the stress case.

## Safety review

- Existing user artwork, source images, and temporary files remain unstaged and unmodified by
  the sprint commit.
- Asset lookup failure is cached and cannot alter gameplay rules or entity construction.
- The renderer is read-only with respect to gameplay snapshots; rendering parity is tested.
- No balance, AI, reward, RL, map content, or observation-schema change was introduced.

## Decision

Sprint S3 meets its exit criteria and is approved for commit. Sprint S4 may begin after the S3
commit is created successfully.
