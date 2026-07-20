# Technology Tree Contracts

Date: 2026-07-20
Plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Status: approved implementation contract for S1-S9

This document fixes the simulation rules that must remain stable while the expanded faction
technology trees are implemented. Numeric values introduced by the plan are provisional and live
only in the canonical content registry. AI, balance tuning, reward design, and RL interfaces remain
out of scope.

## Content and production ownership

- `BuildingDefinition.produces` is the only authoritative producer graph.
- A unit definition does not name a producer. Reverse producer lookup is derived once by the
  registry in canonical building-ID order.
- A train request is valid only when the producer's immutable definition contains the unit ID,
  requirements are complete, population is available, and the team can pay the cost.
- Behavior classes describe mechanics. Serialized IDs, UI labels, observations, factories, and
  maps refer only to concrete content definitions.

## Upgrade definitions and effective stats

An upgrade definition has a stable ID, English display text, faction, resource cost, research
duration, researching buildings, requirements, one optional exclusive group, affected content IDs,
typed stat modifiers, and optional granted ability IDs. Invalid references and requirement cycles
make registry construction fail.

Modifiers use integer additions and integer numerator/denominator multipliers. Denominators must be
positive. Effective stats are always recomputed from immutable base definitions, applying completed
upgrades in sorted upgrade-ID order. The simulation never compounds modifiers onto previously
modified values.

Research completion updates affected living units in stable `entity_id` order. Future spawns use
the same derivation path. An increase to maximum life, shield, or energy preserves damage/depletion
by adding the capacity delta; a decrease clamps the current value. Active attack and ability
cooldowns are not reset.

## Team research state and exclusivity

- Completed upgrades, queued reservations, and unlocked abilities belong to the team.
- An upgrade may be completed or reserved only once.
- All requirements and exclusions are checked atomically before resources are paid.
- An exclusive group is reserved when its job is enqueued. A competing choice cannot enter any
  research queue while that reservation exists.
- Canceling a queued or active research job releases its reservation and refunds 75% of its
  canonical cost, matching the production refund policy.
- Destruction of the researching building removes its activity queue without a refund, matching
  current unit-production semantics. Completed research is permanent.
- Serialization and iteration of research state are sorted by canonical content ID.

## Building activity queue

Unit production and research are typed jobs in one FIFO building activity queue. A building works
on at most one job per frame. Unit completion still emits `(producer, unit)` for rally processing;
research completion emits a typed upgrade-completion event. Cancellation targets a queue index and
uses the job definition's refund rule. No idle simulation tick scans every upgrade definition.

## Ability and cast lifecycle

Ability definitions fix targeting mode (entity or ground), ownership filter, range, energy cost,
cooldown frames, duration, radius, maximum affected targets, effect ID, and presentation key.

1. Issuing a cast validates ownership and that the team has unlocked the ability. It does not pay
   energy or start cooldown.
2. A queued cast stores only canonical IDs or an immutable ground position. Entity targets follow
   their current position while alive; ground targets never move.
3. The caster moves deterministically into range. A normal non-shift command replaces the order;
   Shift appends it.
4. Immediately before effect application, the simulation validates life, target legality, range,
   current energy, and cooldown again.
5. Energy is deducted and cooldown starts only when the effect is successfully applied. A dead or
   invalid target is skipped with no cost. An insufficient-energy order waits; cooldown advances in
   simulation frames only.
6. Area queries use the spatial index, then stable `entity_id` ordering, then the definition's
   target cap. There is no random target choice.
7. Temporary effects store an expiry frame and source upgrade/effect ID. Reapplying the same effect
   refreshes duration and keeps the stronger magnitude; it never stacks without a definition that
   explicitly permits stacking. Expired effects are removed in stable entity order.

The windowed presentation may only create commands for rendered, selectable entities. Once a
command enters the pure simulation, cast legality depends only on deterministic ownership, life,
range, research, energy, and cooldown state. The plan does not add a new fog-of-war simulation.

## Doctrine behavior contracts

Each faction has one mutually exclusive group for each shared archetype.

| Group | Choice | Required gameplay identity |
|---|---|---|
| AEGIS Knight | Bulwark | durable line holder with shield/mitigation support |
| AEGIS Knight | Vanguard | deliberate engage and charge pressure |
| AEGIS Archer | Longshot | setup-dependent reach and precision |
| AEGIS Archer | Arcshot | marked/linked target pressure without poison |
| AEGIS Mage | Shieldweaver | shield restoration and Barrier Pulse support |
| AEGIS Mage | Arcbinder | precision control through Arc Bind |
| RUST Knight | Frenzy | stronger low-health aggression |
| RUST Knight | Pack | benefits from nearby allied pressure |
| RUST Archer | Venom | poison and attrition |
| RUST Archer | Skirmisher | mobile ranged pressure with a weaker dead zone |
| RUST Mage | Plaguecaller | Toxic Cloud area denial and damage over time |
| RUST Mage | Mutagenist | Mutagenic Surge for temporary allied swarm pressure |

Doctrine mechanics must be data-selected and team-owned. Concrete unit code may implement a typed
mechanic, but it may not branch on faction name or doctrine display text.

## Determinism and compatibility

The existing golden replay remains unchanged unless a reviewed change intentionally alters an
existing command path. A separate technology replay is added when doctrines become playable. Every
registry, entity, target, queue, and modifier traversal uses canonical ID or stable entity order.
Headless simulation never imports Pygame or loads visual assets.

## Required fixtures

Implementation sprints must add focused fixtures covering: two producers for one unit; requirements
and cycles; atomic exclusive reservations; cancellation and destruction; existing and future unit
recomputation; maximum-stat preservation; canonical modifier order; queue interaction; interrupted,
queued, invalid, and successful casts; energy/cooldown timing; deterministic capped areas; temporary
effect refresh and cleanup; and windowed rendering for every registered content ID.
