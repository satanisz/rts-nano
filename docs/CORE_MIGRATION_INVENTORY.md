# Core Migration Inventory

Last updated: 2026-07-19
Baseline commit: `cc100d6`

This inventory freezes the pre-registry architecture for Executive Plan 05. It is a migration
checklist, not a target design. Every duplicated source listed below must be removed or reduced
to an adapter by S2.

## S4 progress

The canonical gameplay values listed in the original inventory live in `content/` as immutable
definitions exposed through `ContentRegistry`. Concrete entity classes retain behavior but
receive all runtime stats from definitions.

S2 removed all historical runtime rosters, `FACTION_BY_TEAM`, color-based faction selection,
class-to-roster routing, and the temporary `game/data.py` facade mappings. `EntityStore` is now
the sole runtime collection and indexes stable entity IDs by team, category, and content ID.
`EntityFactory` is the single definition-to-runtime-class boundary used by map loading,
production, and construction. Every shipped map uses schema version 2 and declares each team's
faction explicitly.

S3 moved entity models to `simulation/entities/` and removed image surfaces, portraits, drawing,
asset paths, file I/O, sprite facing, and Pygame time from them. `PygameAssets` now resolves and
caches sprites, portraits, and flipped variants through `visual_key`. Projectile effects and hit
flash timing are presentation-owned and driven by bounded `AttackLanded` output events. Headless
entity construction no longer uses a `load_visuals` flag. The remaining Pygame boundary debt is
manager/application state and terrain geometry assigned to S4.

S4 completed the boundary. `simulation/geometry.py` replaces Pygame rectangles with tested SDL-
compatible clipping semantics. Terrain drawing, click markers, projectiles, asset caches, input,
and command-panel state live under presentation adapters. `SimulationRunner` owns deterministic
system order, ticks, and bounded output events. The former `GameManager` module was removed;
`application/GameSession` composes the runner with camera, menu, pause, selection, and viewport
state. Headless import and construction neither import Pygame nor configure SDL.

## Stable vocabulary

| Term | Meaning | Runtime representation in S0 |
|---|---|---|
| `content_id` | Stable ID of a unit, building, or resource definition | `ContentId(str)` |
| `entity_id` | Stable identity of one runtime entity | `EntityId(int)` assigned once by `EntityStore` |
| `team_id` | Team identity independent of color | `TeamId(str)` |
| `faction_id` | Explicit faction assigned to a team | `FactionId(str)` |
| `unit` | Mobile team-owned entity | `EntityCategory.UNIT` |
| `building` | Stationary team-owned entity | `EntityCategory.BUILDING` |
| `resource` | Neutral harvestable entity | `EntityCategory.RESOURCE` |
| `combat_role` | Definition-level behavior role | `CombatRole` |

## Current definition sources

| Source | Owns today | Duplication or coupling to remove |
|---|---|---|
| `game/data.py::UNIT_SPECS` | Cost, production time, population, producer, faction, legacy roster | Unit classes separately own combat and movement stats. |
| `game/data.py::BUILDING_SPECS` | Cost, build time, footprint, population, products, faction, tech requirements | Building classes separately own life, radius, tower stats, and mechanic stats. |
| `game/assets/entities/units.py` | Size, radius, movement, life, combat, shield, poison, frenzy, splash | Values must move into `UnitDefinition`; classes retain behavior only. |
| `game/assets/entities/buildings.py` | Size, radius, life, tower combat and faction mechanics | Values must move into `BuildingDefinition`. |
| `game/assets/entities/resources.py` and `Resource` | Amount, size, radius, asset paths | Gameplay values move into `ResourceDefinition`; art moves to presentation. |
| `game/constants.py` | Global combat/movement timing and colors | Gameplay constants remain core; colors move to presentation. |
| `game/data.py::FACTION_BY_TEAM` | Blue/Red faction assignment | Replaced by explicit map/team `faction_id` in S2. |

## Migrated creation paths

| Creation path | Registry/factory now | Destination now |
|---|---|---|
| Map loading | `EntityFactory` plus `ContentRegistry` | `EntityStore.add`. |
| Unit production | `EntityFactory` plus producer definition | `EntityStore.add`. |
| Building construction | `EntityFactory` plus constructable definition | `EntityStore.add`. |
| Map editor | Registry-backed schema keys | Schema-versioned per-type coordinate lists. |
| Command panel | Registry definition queries | Manager production/construction helpers. |

## Removed runtime rosters

The former `EntitiesGroup` and `ResourcesGroup`, including the `bases`, `barracks`, `houses`,
`mage_towers`, `towers`, `peasents`, `knights`, `archers`, `mages`, `woods`, and `golds`
collections, have been deleted. Runtime queries use `EntityStore` indexes and preserve entity
creation order.

## Current Pygame boundary debt

Direct Pygame imports in non-UI game modules are forbidden by
`tests/test_architecture_boundaries.py`; the debt allowlist is now empty. The simulation, terrain,
application session, and headless entry points are fresh-process tested to remain Pygame-free.
UI, `main.py`, and the map editor remain presentation/application code.

## Migration ownership

| Sprint | Removes |
|---|---|
| S1 | Duplicated stats and spec/factory design data. |
| S2 | Legacy rosters, class-to-roster routing, color-to-faction mapping. |
| S3 | Art, file I/O, drawing, and Pygame time from entities. |
| S4 | Pygame geometry, VFX, camera, and presentation state from simulation orchestration. |
