# Core Migration Inventory

Last updated: 2026-07-19
Baseline commit: `cc100d6`

This inventory freezes the pre-registry architecture for Executive Plan 05. It is a migration
checklist, not a target design. Every duplicated source listed below must be removed or reduced
to an adapter by S2.

## S1 progress

The canonical gameplay values listed in the original inventory now live in `content/` as
immutable definitions exposed through `ContentRegistry`. `game/data.py` is a temporary legacy
facade only; its mappings are read-only views of the registry and contain no independent values.
Concrete entity classes retain behavior but receive all runtime stats from definitions.

The remaining factory-to-class and factory-to-roster mappings are intentionally assigned to S2,
together with historical rosters and `FACTION_BY_TEAM`.

## Stable vocabulary

| Term | Meaning | Runtime representation in S0 |
|---|---|---|
| `content_id` | Stable ID of a unit, building, or resource definition | `ContentId(str)` |
| `entity_id` | Stable identity of one runtime entity | `EntityId(int)`; assignment begins in S2 |
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

## Current creation paths

| Creation path | Registry/factory today | Destination today |
|---|---|---|
| Map loading | `manager.EntityFactory._TEAM_ENTITY_TYPES` and `_NEUTRAL_ENTITY_TYPES` | Pattern matching in `GameManager._load_map_settings`. |
| Unit production | `ProductionSystem._UNIT_FACTORIES` | `UnitSpec.roster_attribute` plus `getattr`. |
| Building construction | `ConstructionSystem._BUILDING_FACTORIES` | `_BUILDING_ROSTERS` plus `getattr`. |
| Map editor | Tool/type tables in `map_editor.py` and schema keys | Serialized per-type coordinate lists. |
| Command panel | Spec queries plus selection class checks | Manager production/construction helpers. |

## Current runtime rosters

`EntitiesGroup` owns `bases`, `barracks`, `houses`, `mage_towers`, `towers`, `peasents`,
`knights`, `archers`, and `mages`. Faction units subclass historical classes so they fit these
lists. `ResourcesGroup` separately owns `woods` and `golds`.

S2 replaces these with one stable `EntityStore` and indexes by team, category, and content ID.

## Current Pygame boundary debt

Direct Pygame imports in non-UI game modules are locked by
`tests/test_architecture_boundaries.py`:

- `game/assets/entities/base_entities.py`,
- `game/manager.py`,
- `game/terrain.py`.

The allowlist may only shrink. S3 removes entity dependencies; S4 removes manager and terrain
dependencies. UI, `main.py`, and the map editor remain presentation/application code.

## Migration ownership

| Sprint | Removes |
|---|---|
| S1 | Duplicated stats and spec/factory design data. |
| S2 | Legacy rosters, class-to-roster routing, color-to-faction mapping. |
| S3 | Art, file I/O, drawing, and Pygame time from entities. |
| S4 | Pygame geometry, VFX, camera, and presentation state from simulation orchestration. |
