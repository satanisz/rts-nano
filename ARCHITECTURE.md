# RTS Nano Architecture

RTS Nano has one deterministic game simulation. The windowed game and headless callers compose the
same core; rendering is an optional adapter, not a second implementation of the rules.

## Dependency direction

```text
content definitions ──► simulation entities ──► gameplay systems
                                                │
                                                ▼
                                      application/GameSession
                                        │               │
                                        ▼               ▼
                                  Pygame input      Pygame rendering

headless wrapper ───────────────────────► same GameSession and SimulationRunner
```

Core modules never import presentation modules or Pygame.

The RL environment adds typed actions and serializable snapshots above the same `GameSession`,
`OrderSystem`, and `SimulationRunner`; it is not a second simulation.

## Content

`src/rts_nano/content/` is the single source of truth for unit, building, resource, faction, and
production definitions. Definitions are immutable and validated when `ContentRegistry` is built.
`EntityFactory` maps a definition's behavior key to a runtime class; numeric gameplay values do not
live in factories, UI tables, or concrete constructors.

## Simulation

- `simulation/entities/` owns pure entity state and local behavior such as movement, attacks,
  shields, poison, frenzy, and splash resolution.
- `simulation/runner.py` owns deterministic tick order and the bounded output-event queue.
- `simulation/geometry.py` provides pure rectangle and line-clipping behavior.
- `game/state.py` owns teams, the generic `EntityStore`, terrain, fog data, tick count, and spatial
  and obstacle revisions.
- `game/` systems own movement/pathfinding, orders, construction, production, gathering, combat,
  effects, victory, observations, and terrain rules.

`EntityStore` is the only runtime registry. It assigns monotonic entity IDs and exposes stable
indexes by team, category, and content ID. The spatial grid is a proximity accelerator, not entity
ownership.

## Application and presentation

`application/GameSession` composes state, systems, simulation, and player-facing application state.
Selection, current team, pause, camera, menus, and viewport state live here rather than in the
simulation.

`game/ui/` owns Pygame input, rendering, terrain drawing, cached image/font resources, command
panels, projectiles, click markers, and other visual effects. Rendering reads simulation state and
events but does not change gameplay state.

`main.py` owns Pygame startup, window/fullscreen creation, the outer event loop, and presentation
composition. `headless.py` constructs the same `GameSession` without importing Pygame or SDL.
Match restart is also an application-shell responsibility: a fresh `GameSession` is created from a
deep copy of the original map settings, while renderer-owned asset caches are retained and only
match-local presentation effects are cleared.

## Tick order

One `SimulationRunner.step()` performs:

1. increment tick and clear the previous tick's output events;
2. capture stable entity creation order and update terrain height levels;
3. update units, gathering, paths, local collisions, and incremental spatial cells;
4. advance construction and production;
5. apply producer rally points and advance completed unit-order queues;
6. resolve tower combat and timed effects;
7. remove dead entities and publish obstacle revisions;
8. update victory state.

Presentation consumes the resulting state and attack events after the simulation step.

## Orders and production handoff

`OrderSystem` is the single high-level command boundary for both Pygame and headless callers.
Units hold one active order and a bounded queue of at most 16 deferred orders. A normal command
replaces the active intent and clears that queue; a Shift command appends movement, attack-move,
patrol, target attack, gather, return-cargo, build/repair, or Mage cast work.
Construction is an active `build` order, so queued gathering starts only after the worker finishes
or the unfinished building is canceled. Only units with non-empty queues are tracked for per-tick
advancement.

## Headless RL boundary

`env.py` owns episode lifecycle, scalar legacy stepping, simultaneous joint stepping, action masks,
and team reward calls. `action_translation.py` validates snapshot IDs and delegates commands to the
same `OrderSystem`, `ProductionSystem`, `ConstructionSystem`, `UpgradeSystem`, and `AbilitySystem`
used by the playable game. `joint_actions.py` normalizes both teams against one pre-step state and
reserves bounded resource, research, and placement claims before mutation.

`game/observations.py` is a serializable read boundary, not a second state store. Schema v4 exposes
stable entity IDs, factions, upgrade/activity state, Mage energy/cooldowns/abilities, and current
orders. The environment does not import Pygame, load assets, select entities, or require a tensor
framework. The windowed `ScriptedAI -> GameSession.update()` path remains independent of it.

Bases store a simulation-owned move or gather rally order. `ProductionSystem` reports newly spawned
units to `SimulationRunner`, which asks `OrderSystem` to apply the producing Base's rally. A missing
or depleted resource target resolves to the nearest live node of the same content type.

## Coordinates and collision

Gameplay uses world coordinates. Rendering subtracts camera offset to produce screen coordinates;
HUD and menus use screen coordinates. Terrain, building obstacles, spatial cells, paths, targets,
and orders always use world coordinates.

The map's declared width and height are authoritative simulation bounds. Viewport and window sizes
are presentation state and never enlarge or otherwise mutate the world.

Water and rocks block movement. Resources intentionally do not. Buildings are dynamic obstacles:
creation/removal increments an obstacle revision, and active paths recalculate once against the new
world. Unreachable orders stop deterministically rather than retrying forever.

## Maps

MapSpec v3 is the semantic authoring boundary. `map_spec.py` validates named anchors, patterns,
mirrors, terrain, and strategic requirements, then deterministically compiles them to runtime v2
`MapSettings`. `map_schema.py` is the shared v2/v3 loader boundary. Simulation code sees only the
compiled v2 shape and does not depend on authoring metadata or Pygame.

`map_tools.py` provides pure text inspection and SVG preview generation. Existing runtime v2 maps
remain supported during incremental migration; the current visual editor is v2-only to prevent a
v3 source from being destructively flattened on save.

## Ownership rules

- Add canonical content and stats in `content/registry.py`.
- Add a concrete entity behavior only when the behavior is genuinely new.
- Add cross-entity rules to a focused system in `game/`.
- Add tick orchestration and pure output events to `simulation/`.
- Add input, surfaces, sprites, VFX, camera, or HUD behavior to `game/ui/` or `application/`.
- Add upgrades and abilities to `content/registry.py`; derive player-facing graph rows through
  `game/ui/tech_tree.py` instead of maintaining a parallel presentation graph.
- Add runtime schema validation to `map_schema.py`, semantic authoring rules to `map_spec.py`, and
  editor-only behavior to `map_editor.py`.
- Never make simulation code conditional on whether a renderer exists.

See [Adding Content](docs/ADDING_CONTENT.md), [Technology and Ability Authoring](docs/TECH_TREE_AUTHORING.md),
and [Determinism](docs/DETERMINISM.md) for extension contracts.
