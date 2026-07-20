# Adding Game Content

Gameplay content is definition-first. A normal new unit or building should require one canonical
definition, an asset mapping supplied by that definition, and tests. Do not add parallel stat
tables, faction rosters, factory branches, or UI price tables.

Upgrade and active-ability additions follow the separate
[Technology and Ability Authoring](TECH_TREE_AUTHORING.md) contract. Their English F9 view is
generated from the same registry definitions.

## Add a unit

1. Add one immutable `UnitDefinition` in `src/rts_nano/content/registry.py` with its ID, faction,
   visual key, behavior key, cost, requirements, and every gameplay stat.
2. Reuse an existing behavior in `simulation/entities/` when the unit follows existing rules.
   Create a new concrete behavior class only for a genuinely new mechanic, then register that
   behavior once in `game/entity_factory.py`.
3. Add the sprite and portrait files addressed by `visual_key`. Presentation asset lookup is
   optional to simulation construction and must never alter stats or rules.
4. Add the unit ID to every producing building's `produces` tuple and to each faction roster that
   can use it. Building tuples are the only authoritative producer graph; use
   `CONTENT.producers_for_unit(...)` for deterministic reverse lookup.
5. Add a table-driven definition/runtime parity test and an asset-completeness case. Add a focused
   behavior test only when the mechanic is new.

## Add a building

Follow the same process with one `BuildingDefinition`. Define footprint, cost, construction time,
population, production, requirements, attack behavior, and visuals in the registry. Reuse the
generic construction and placement systems. Add a factory behavior only for a new building rule.

## Add a resource or faction

Resources use `ResourceDefinition` and remain nonblocking unless the global gameplay rule is
explicitly changed with path/collision tests. A faction definition lists valid unit/building IDs;
team color remains independent and maps select the faction with `faction_id`.

## Validation checklist

- `CONTENT` builds without duplicate IDs or invalid references.
- Runtime stats equal the immutable definition.
- Map validation accepts the content only for valid faction assignments.
- Headless import and construction do not load Pygame or image files.
- The deterministic replay changes only when an approved gameplay change requires a documented
  rebaseline.
- Ruff, format, Ty, pytest, map validation, and rendering smoke all pass.
