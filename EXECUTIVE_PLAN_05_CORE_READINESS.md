# RTS Nano — Executive Plan 05: Game Core Readiness

Last updated: 2026-07-19

## STATUS: IN PROGRESS — S3 COMPLETE

Sprints S0 through S3 completed on 2026-07-19. Gameplay definitions have one validated source of
truth, runtime state uses one stable generic entity store with explicit team factions, and entity
models are now pure simulation objects with presentation-owned Pygame assets and effects. Runtime
behavior remains identical to the S0 golden replay. See `docs/reviews/`. Sprint S4 is next.

Goal: bring the current game to a **game-core-complete state suitable for later AI and RL work**.
“Complete” does not mean a commercial product, campaign, or polished HUD. It means:

- the current gameplay rules work deterministically,
- unit, building, resource, and faction definitions have one source of truth,
- simulation does not depend on Pygame or presentation state,
- adding content does not require edits across several factories and legacy rosters,
- performance has measurable budgets and regression protection,
- documentation and CI describe and enforce the target architecture.

This plan starts after commit `cc100d6`, which delivered:

- visual asset caching and `load_visuals=False`,
- headless execution without SDL initialization,
- a spatial grid for collisions, attack-move acquisition, and towers,
- buildings as dynamic pathfinding obstacles,
- a direct-path fast path,
- 122 passing tests and measured simulation speedups.

---

## 1. Executive decision

Execution order:

`S0 Guardrails → S1 Content Registry → S2 Generic World Model → S3 Pure Entities → S4 Pure Simulation → S5 Hardening → S6 Docs & CI`

AI, balance, and RL integration do not begin before S6 is complete. This prevents agents,
training scenarios, and balance tooling from being built against APIs and entity models that
are about to be replaced.

### Priorities

1. One source of truth for game content.
2. A stable, generic world model.
3. A pure simulation layer without Pygame.
4. Correctness and performance at higher entity counts.
5. Automated architecture and quality protection.

### Out of scope

- training agents, Gymnasium/PettingZoo, and tensor observations,
- rewards, reward factories, `max_steps`, and `terminated`/`truncated`,
- multi-environment RL lifecycle and orchestration,
- expanding `ScriptedAI`, self-play, or additional bot strategies,
- balancing costs, damage, build times, or matchups,
- campaign, save/load, audio, animation, or product-level UI polish,
- new factions or units beyond what is necessary to migrate existing content.

These areas begin only after the S6 completion report is accepted.

---

## 2. Non-negotiable engineering rules

1. **One source of truth.** Stats, costs, producers, tech requirements, category, and faction
   ownership must not be defined in more than one place.
2. **No Pygame in core.** Simulation modules must not import Pygame directly or transitively.
3. **Presentation does not control rules.** Missing art or a disabled renderer cannot alter a
   simulation result.
4. **Stable deterministic ordering.** Entity iteration and combat resolution cannot depend on
   `set` order, hash seed, wall-clock time, or renderer activity.
5. **No balance changes during refactoring.** Migrated definitions retain current values.
6. **Small, reversible steps.** Every sprint ends in its own commit with a green quality gate.
7. **No permanent migration layer.** Compatibility adapters may exist for one sprint only and
   must have a scheduled removal in that same sprint.
8. **Profile before optimizing.** Every performance change requires before/after evidence.

### Required gate after every sprint

```text
ruff check
ruff format --check
ty check
pytest + coverage
validation of every shipped map
deterministic replay
render smoke test
headless benchmark smoke
```

No sprint proceeds when behavior changed without an explicit plan decision.

---

## 3. Target architecture

```text
content/                         simulation/                       presentation/
  definitions.py                  state.py                          pygame_assets.py
  registry.py                     entities.py                       renderer.py
  factions.py                     systems/                          input_controller.py
                                  spatial.py                        camera.py
                                  terrain.py
                                  events.py

                   application/
                     game_session.py
                     map_loader.py
                     main.py
```

### Responsibilities

- `content/` owns immutable gameplay definitions.
- `simulation/` owns deterministic state and rules only.
- `presentation/` owns Pygame, art, fonts, input, camera, and VFX.
- `application/` composes the layers into either a windowed game or a headless process.

The simulation emits events such as `AttackLanded`, `EntityDied`, and
`ConstructionCompleted`. Presentation may turn them into projectiles and effects, but visual
objects never feed back into gameplay rules.

---

## 4. Sprint S0 — Baseline and architectural contracts

**Size:** S
**Goal:** freeze current behavior before structural migration.

### Work

1. Record baseline results for map 01 and the 400-unit stress scenario:
   cold initialization, steps/s, group-order time, and approximate memory usage.
2. Add a versioned deterministic replay covering movement, gathering/depositing,
   construction, production, combat, poison, shields, splash, and victory.
3. Store the final-state digest and produce a readable snapshot diff on failure.
4. Add an import-boundary test intended to forbid Pygame in `simulation/`. In S0 it may list
   current violations as explicitly tracked debt.
5. Document every current factory, roster, and definition source in a migration table.
6. Define stable vocabulary and types for `content_id`, `entity_id`, `team_id`, `faction_id`,
   `unit`, `building`, `resource`, and `combat_role`.

### Exit criteria

- replay produces the same digest in at least two consecutive runs,
- a baseline performance report is tracked in the repository,
- duplicated factories and definition sources are fully inventoried,
- gameplay rules and values remain unchanged.

---

## 5. Sprint S1 — Central Content Registry

**Size:** L
**Goal:** give units, buildings, resources, and factions one source of truth.

### Target definitions

Create pure, Pygame-free definitions including:

- `UnitDefinition`,
- `BuildingDefinition`,
- `ResourceDefinition`,
- `FactionDefinition`,
- `ContentRegistry`.

A unit definition includes at least:

- stable ID, display name, category, and faction or `shared` ownership,
- life, speed, radius, and vision range,
- damage, attack type, range, and cooldown,
- armor, shield, poison, frenzy, and splash parameters,
- cost, population cost, and production time,
- `produced_at`, `requires`, and a behavior key such as `worker`, `melee`, `ranged`, or
  `artillery`.

A building definition includes at least:

- stable ID, faction, category, and collision footprint,
- life and defensive stats,
- cost, build time, and population provided,
- `requires` and `produces`,
- tower attack parameters where applicable.

PNG paths are not gameplay data. Definitions may expose a stable `visual_key`, while
`visual_key → sprite/portrait` mapping remains in presentation.

### Work

1. Replace scattered spec tables with one registry.
2. Move numeric stats out of `Peasant`, `Guardian`, `Marksman`, and other concrete classes.
3. Keep classes as behaviors backed by injected definitions, without local stat constants.
4. Validate the registry for:
   - unique IDs,
   - valid tech requirements and producers,
   - no tech-tree cycles,
   - faction roster consistency,
   - positive footprints and durations.
5. Move production, construction, command-panel, and observation queries to the registry.
6. Add table-driven tests for every existing content type.
7. Remove duplicated costs, timings, and stats from helper mappings and classes.

### Exit criteria

- changing one gameplay value requires editing exactly one definition,
- production and construction contain no private stat tables,
- all values match the S0 baseline,
- registry modules do not import Pygame or presentation classes,
- deterministic replay remains identical.

Legacy rosters remain temporarily in S1 and are removed in S2.

---

## 6. Sprint S2 — Generic entity, team, and faction model

**Size:** L
**Goal:** remove legacy rosters and the hardcoded `Blue → AEGIS`, `Red → RUST` mapping.

### Work

1. Introduce stable simulation-owned `EntityId` values.
2. Replace per-class lists with one `EntityStore` containing:
   - `entity_id → entity` as the primary index,
   - team index,
   - category index (`unit`, `building`, `resource`),
   - optional `content_id` index for frequent queries.
3. Guarantee stable iteration independent of hash seed.
4. Replace `peasents`, `knights`, `archers`, `mages`, `barracks`, and similar rosters with
   `units_for_team`, `buildings_for_team`, and `entities_by_content_id` queries.
5. Migrate systems, selection, UI, victory, and observations to the new query API.
6. Remove class matching from map loading and manual roster selection.
7. Add explicit `faction_id` to team setup.
8. Version and migrate all three maps so team color no longer selects faction.
9. Remove `FACTION_BY_TEAM` and color-based fallbacks.
10. Add tests for swapped factions and for two teams using the same faction.

### Exit criteria

- no runtime rosters named after historical classes,
- factories never choose a destination list for a new entity,
- maps define team factions explicitly,
- Blue can use RUST and Red can use AEGIS without code changes,
- standard map behavior still matches the baseline.

Any temporary compatibility properties introduced in S2 must be removed before S2 closes.

---

## 7. Sprint S3 — Pure simulation entities

**Size:** L
**Goal:** make gameplay entities unaware of images, fonts, drawing, and Pygame.

### Work

1. Move simulation entity models into the `simulation` layer.
2. Remove from gameplay entities:
   - `pygame.Surface`,
   - image and portrait fields,
   - `load_image()` and asset caches,
   - `draw()`, placeholder glyphs, and sprite flipping,
   - `pygame.time.get_ticks()`.
3. Replace hit flash with a simulation event or a presentation timer based on simulation tick.
4. Move image caching to `presentation/pygame_assets.py`.
5. Resolve sprite and portrait through `visual_key`/`content_id`, not entity fields.
6. Cache presentation variants such as normal and horizontally flipped sprites.
7. Keep a missing-art fallback that cannot affect simulation.
8. Test that identical commands produce identical results with and without presentation.
9. Add a render smoke test for every content definition.

### Exit criteria

- simulation entity modules do not import Pygame,
- entity creation performs no file I/O,
- missing art cannot change game state,
- the windowed game still renders every current content type,
- headless construction no longer requires a visual-loading flag.

After S3, `load_visuals=False` can disappear from core. Headless behavior is selected by not
constructing a presentation adapter, rather than by a flag inside `GameState`.

---

## 8. Sprint S4 — Pure simulation and thin Pygame application

**Size:** XL
**Goal:** run the complete game tick without Pygame and remove presentation state from the
simulation coordinator.

### Work

1. Introduce `Simulation`/`SimulationRunner`, owning:
   - `GameState`,
   - content registry,
   - gameplay systems,
   - tick counter,
   - input command queue,
   - output event queue.
2. Move tick orchestration out of `GameManager.update()`.
3. Replace `pygame.Rect` terrain geometry with pure geometry types and functions.
4. Preserve water, rocks, ramps, high ground, and segment collision semantics.
5. Keep fog as pure grid data or move render-only fog state to presentation, depending on
   whether the information is part of gameplay rules.
6. Remove `MagicMissile`, `ArcherShot`, and `ClickMarker` from simulation ownership.
7. Move camera, selection rectangle, menu state, and mouse state to the Pygame application.
8. Keep a thin `GameSession` that composes simulation, input, and rendering.
9. Reconnect `HeadlessSimulation` without changing its public operations used by tests.
10. Add a fresh-process import test proving pure simulation does not load `pygame`.
11. Remove `GameManager` or retain it only as a temporary compatibility facade.

### Exit criteria

- headless works without importing or initializing Pygame,
- core contains no drawing, input, camera, menu, or VFX objects,
- windowed play uses the same simulation rather than a second rules implementation,
- deterministic replay remains identical unless a separately approved bug fix requires one
  documented rebaseline,
- renderer can be omitted without conditional branches inside the simulation tick.

Split S4 into reviewable commits: geometry → events/VFX → simulation runner → game session →
compatibility-layer removal. Run the complete gate after every commit.

---

## 9. Sprint S5 — Correctness, scaling, and performance hardening

**Size:** L
**Goal:** close technical gameplay risks before AI and RL begin.

### Correctness work

1. Refresh spatial indexes correctly after spawn, construction, death, and cancellation.
2. Test high-speed movement across spatial cells.
3. Test splash damage across cell boundaries.
4. Test towers, attack-move, and collisions at map boundaries.
5. Add deterministic safe unit spawning near producers:
   - never inside a building,
   - never in water or rocks,
   - nearest valid point selected deterministically,
   - explicit behavior when no spawn point exists.
6. Invalidate or recalculate paths when a building creates or removes an obstacle.
7. Define unreachable-target behavior instead of infinite stuck/repath loops.
8. Record and test the intentional rule that resources do not block movement.

### Performance work

1. Profile separately:
   - world creation,
   - group command assignment,
   - movement and collisions,
   - target acquisition,
   - pathfinding and repathing,
   - observation-independent core tick.
2. Remove remaining hot global scans when profiling justifies the change.
3. Reduce repeated `all_entities` construction and temporary tick allocations.
4. Consider path caching or flow fields for large groups only after measurement.
5. Track benchmarks for:
   - idle map 01,
   - active economy,
   - two-army combat,
   - 400 dispersed units,
   - 400 units in close combat.
6. Establish budgets from medians with CI-safe tolerance.
7. Track allocation and memory behavior for initialization and long headless matches.

### Initial performance constraints

- no return to O(N²) scans for dispersed units,
- local map 01 cold initialization without presentation remains below 20 ms,
- the standard benchmark does not regress below the `cc100d6` baseline,
- the 400-unit stress case retains at least a 4× advantage over global scanning,
- long headless runs do not retain an unbounded number of events or visual objects.

### Exit criteria

- every correctness case above has a test or benchmark,
- no known deadlock remains around dynamic building obstacles,
- spawn and repath behavior is deterministic,
- benchmark report shows no significant regression from S0.

---

## 10. Sprint S6 — Documentation, CI, and stage closure

**Size:** M
**Goal:** make the repository describe and protect the completed game core.

### Documentation

1. Rewrite README for the current game, factions, and launch commands.
2. Update `ARCHITECTURE.md` to the real content/simulation/presentation/application split.
3. Update `MAP_SCHEMA.md` with `schema_version`, `team_id`, and `faction_id`.
4. Add a “How to add content” guide where a new unit requires:
   - one definition,
   - an optional behavior only when genuinely new,
   - presentation asset mapping,
   - a definition test.
5. Document determinism guarantees and stable entity ordering.
6. Document benchmarks and how to interpret them.
7. Mark Executive Plan 05 COMPLETE with actual commits and measured results.

### CI

1. Add a quality workflow for Ruff check, Ruff format check, and Ty.
2. Add a test workflow for pytest, coverage, replay digest, and all map validators.
3. Add a render smoke test using the dummy video driver.
4. Add a fast benchmark smoke job. Initially report results; enforce a threshold only after
   runner variance has been measured.
5. Cache uv and dependencies, not test results.
6. Run workflows on pushes and pull requests.

### Exit criteria

- a clean checkout passes CI without manual setup,
- documentation no longer describes legacy Knight/Archer/Mage as the current roster,
- adding a unit does not require edits to several factories,
- no document points to a nonexistent `EXECUTIVE_PLAN.md`,
- the completion report confirms readiness for a separate AI/RL plan.

---

## 11. Definition of Done

Executive Plan 05 is complete only when:

- all current units, buildings, resources, and factions are defined in one registry,
- gameplay values are not duplicated across classes, factories, and UI,
- runtime uses a generic `EntityStore`, not historical rosters,
- team faction is explicit and independent of color,
- simulation and its tests do not import Pygame,
- the windowed game is an adapter over the same pure simulation,
- spatial grid, pathfinding, spawn, and repath have boundary tests,
- deterministic replay remains stable,
- benchmarks show no regression from baseline,
- README, architecture, and map schema are current,
- CI runs the quality gate automatically,
- AI, balance, and RL work has not begun prematurely.

---

## 12. Main risks and controls

| Risk | Control |
|---|---|
| Registry becomes a new monolith | Keep definitions small and immutable; behaviors remain in systems. |
| Roster migration changes combat order | Stable `EntityId`, explicitly ordered indexes, replay after every commit. |
| Removing Pygame changes geometry | Comparative tests for ramps, water, rocks, intersections, and boundaries. |
| Renderer starts owning gameplay rules | Renderer reads snapshots and events but never writes to `GameState`. |
| Refactor is too large to review | Split S3 and S4 into small commits with a working game after each step. |
| CI benchmark is noisy | Use medians, wide tolerance, and report-only mode before enforcing thresholds. |
| AI or balance expands scope | Move every such task into the next executive plan. |

---

## 13. Next stage

After S6, create Executive Plan 06 covering:

1. deterministic baseline AIs,
2. automated balance simulations,
3. multi-environment lifecycle,
4. reward factories and episode limits,
5. training-oriented observations and actions,
6. RL adapters and self-play.

Plan 06 must build on the completed registry and pure simulation rather than adding workarounds
for the current architecture.
