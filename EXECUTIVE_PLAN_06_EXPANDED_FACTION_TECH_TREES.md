# RTS Nano — Executive Plan 06: Expanded Faction Tech Trees

Last updated: 2026-07-20

## STATUS: IN PROGRESS — S2 COMPLETED

This plan expands the completed RTS game core with shared baseline and tier-two combat units,
deterministic team-wide research, mutually exclusive faction doctrines, a deterministic caster
ability model, and an English tech-tree interface. It starts after commit `67775bc`, with 235
passing tests and the game-core architecture complete.

The plan deliberately moves AI, numeric balance tuning, and RL integration to Executive Plan 07.
It supersedes the old Plan 05 suggestion that AI/RL should immediately become Plan 06: the game now
receives its final technology layer first, so later agents train against stable rules and actions.

---

## 1. Executive decision

Execution order:

`S0 Contracts → S1 Behavior Classes → S2 Multi-Producer Content → S3 Knight, Archer, and Mage → S4 Upgrade Core → S5 Research Flow → S6 Caster Abilities → S7 AEGIS Doctrines → S8 RUST Doctrines → S9 Tech UI and Closure`

Every sprint ends with:

1. focused implementation tests;
2. architectural and gameplay review;
3. the complete quality gate;
4. the headless benchmark;
5. one review document;
6. one commit before the next sprint begins.

### Target outcome

- `Knight`, `Archer`, and `Mage` are real shared units available to AEGIS and RUST.
- Gameplay behavior bases have semantic names and are not named after content.
- One unit may be trained by multiple faction buildings without duplicated definitions.
- Research is deterministic, cancellable, visible, and owned by the pure simulation.
- Upgrades are team-wide and recomputed from canonical definitions rather than applied repeatedly.
- Each faction gives Knight, Archer, and Mage two mutually exclusive doctrine builds.
- Mage is a shared tier-two caster with deterministic energy, cooldown, targeting, and ability
  rules; it is not the behavior parent of Arclight.
- Existing faction units remain advanced alternatives rather than renamed copies of shared units.
- The completed tree is usable through the windowed game without introducing RL-specific code.

### Out of scope

- ScriptedAI changes, build-order logic, self-play, or automated strategy selection.
- Reward changes, RL actions, tensor observations, wrappers, or environment lifecycle work.
- Automated balance simulations or final cost/stat tuning.
- Individual-unit experience, veterancy, talent points, or per-unit promotion.
- New factions, campaign progression, save/load, audio, or product-level UI polish.
- Replacing Guardian, Marksman, Arclight, Ripper, Spitter, or Brute.

---

## 2. Product and architecture decisions

### 2.1 Shared units, faction-owned doctrines

`Knight`, `Archer`, and `Mage` use shared content IDs and shared baseline definitions. Both faction
rosters include them, and their producer relationship is many-to-many:

| Shared unit | AEGIS producer | RUST producer |
|---|---|---|
| Knight | Arsenal | Pit |
| Archer | Arsenal | Pit |
| Mage | Spire | Chem-Vat |

The shared baseline remains understandable and useful without research. Faction identity comes
from team-wide doctrine choices, existing advanced units, and faction buildings—not from hidden
team-color conditionals in entity classes.

### 2.2 Behavior classes are not content classes

Target hierarchy:

```text
Unit
├── MeleeUnit
│   ├── Knight
│   ├── Guardian
│   ├── Ripper
│   └── Brute
├── DeadZoneRangedUnit
│   ├── Archer
│   ├── Marksman
│   └── Spitter
├── CasterUnit
│   └── Mage
└── ArtilleryUnit
    └── Arclight
```

`MeleeUnit`, `DeadZoneRangedUnit`, `CasterUnit`, and `ArtilleryUnit` describe reusable rules.
`Knight`, `Archer`, `Mage`, and the faction units are concrete content implementations. Arclight is
artillery rather than a subclass of Mage. No map, factory, UI, or observation may expose a
behavior-class name as a content ID.

### 2.3 Team-wide, mutually exclusive doctrines

Research affects all existing and future units of the targeted content type. Knight/Archer/Mage
builds are not selected per unit. Each faction has one exclusive choice slot per shared archetype:

```text
AEGIS Knight: Bulwark Doctrine XOR Vanguard Doctrine
AEGIS Archer: Longshot Doctrine XOR Arcshot Doctrine
AEGIS Mage:   Shieldweaver Doctrine XOR Arcbinder Doctrine
RUST Knight:  Frenzy Doctrine XOR Pack Doctrine
RUST Archer:  Venom Doctrine XOR Skirmisher Doctrine
RUST Mage:    Plaguecaller Doctrine XOR Mutagenist Doctrine
```

An exclusive choice is atomic: the system validates requirements and exclusions before paying the
cost or entering the queue. A completed doctrine cannot be canceled, replaced, or researched twice.

### 2.4 Deterministic modifiers

- Definitions store integer additions and rational/fixed-point multipliers; gameplay does not
  accumulate floating-point deltas by repeatedly mutating current stats.
- Effective stats are derived from the immutable unit definition plus the team's completed upgrade
  set in canonical upgrade-ID order.
- Completing research recomputes affected living entities once in stable `entity_id` order.
- Newly spawned units receive the same derived stats during creation.
- Max-life or max-shield increases preserve existing damage and add only the new capacity.
- Active attack cooldowns are not reset by research completion.
- Set-like membership may be used for lookup, but serialization and iteration are always sorted.

### 2.5 Research and production share a building activity slot

A production building cannot train a unit and research a technology simultaneously. The current
unit-only production queue will be generalized into a deterministic building activity queue with
typed unit and research jobs. Cancellation refunds the active job according to its own canonical
definition. Unit completion still reports `(producer, unit)` for rally handoff.

### 2.6 Mage is a caster, not generic artillery

Shared Mage is a fragile tier-two support caster with a normal medium-range magic attack and an
integer energy pool. Faction doctrines grant active abilities through canonical definitions.
Arclight remains dedicated long-range artillery with splash and does not inherit Mage, energy, or
caster orders. Spire must choose between Mage/Arclight production and AEGIS research; Chem-Vat must
choose between Mage/Brute production and RUST research through the shared activity queue.

### 2.7 Provisional values are not final balance

This plan requires complete, playable costs, durations, and modifiers, but does not attempt matchup
balance. Initial values are conservative, documented, and centralized. Numeric tuning occurs later
without changing APIs, doctrine identity, queue rules, or behavior contracts.

---

## 3. Faction identity contract

| Axis | AEGIS | RUST |
|---|---|---|
| Army model | fewer durable specialists | numerous aggressive bodies |
| Defense | shields, armor, formation | health pressure, frenzy, expendability |
| Ranged combat | precision, setup, long reach | mobility, poison, attrition |
| Melee combat | holding lines or deliberate charge | pack pressure or low-health aggression |
| Production | higher commitment per unit | faster tempo and replacement |
| Combined arms | target marking and artillery | poison pressure and swarm follow-up |
| Mage role | shield sustain or precision control | toxin area denial or swarm mutation |
| Failure mode | expensive losses and broken formation | weak isolated units and poor sustained defense |

Shared units must remain recognizable as Knight, Archer, and Mage, but their researched play
patterns must diverge enough that the same army composition requires different positioning and
timing by faction. AEGIS Mage controls shield energy and precision setup; RUST Mage spreads toxins,
weakens enemies, or mutates allied swarm units.

---

## 4. Required gate after every sprint

```text
uv run ruff format --check .
uv run ruff check .
uv run ty check src/rts_nano
uv run pytest --cov=src/rts_nano
uv run python -m rts_nano.validate_map <all shipped maps>
uv run python benchmarks/core_baseline.py
```

The gate also includes:

- deterministic replay;
- fresh-process headless import boundary;
- render smoke for every registered content ID;
- registry validation and tech-cycle validation;
- no unexpected working-tree files;
- a sprint review under `docs/reviews/`.

Performance budgets remain:

- idle throughput: at least 6,000 steps/s;
- 400-unit throughput: at least 60 steps/s;
- two 400-unit group orders: below 5,000 ms;
- memory comparable to the established 1.027 MiB 400-unit baseline;
- no all-unit or all-upgrade scan every idle tick.

---

## 5. Sprint S0 — Baseline, rules, and migration contract

**Size:** S
**Goal:** freeze current behavior and approve the exact technology model before structural work.

### Work

1. Record current test, replay, render, map, and benchmark results.
2. Inventory every inheritance dependency on `Knight`, `Archer`, and `Mage`.
3. Record the current reciprocal `UnitDefinition.produced_at` / `BuildingDefinition.produces`
   contract and all production callers.
4. Specify typed upgrade fields, modifier operations, exclusivity groups, refund rules, and
   completion semantics.
5. Specify every doctrine's behavior contract without final balance numbers.
6. Specify ability targeting, energy payment, cooldown start, interruption, area lifetime, and
   temporary-effect cleanup contracts.
7. Add review fixtures for team-wide upgrades, exclusive choices, existing-unit recomputation,
   future spawns, cancellation, casting, and deterministic ordering.
8. Confirm that existing golden replay must remain unchanged through S5; introduce a second
   technology replay when faction doctrines land.

### Exit criteria

- the migration inventory has no unknown class/factory dependency;
- research and modifier semantics are explicit enough to implement without mid-sprint design;
- baseline results are recorded;
- no gameplay or content value changes;
- review accepted and committed.

---

## 6. Sprint S1 — Semantic behavior hierarchy

**Size:** M
**Goal:** separate reusable combat behavior from concrete unit names without changing gameplay.

### Work

1. Rename/refactor `Knight` behavior into `MeleeUnit`.
2. Rename/refactor `Archer` behavior into `DeadZoneRangedUnit`.
3. Replace the old `Mage` behavior parent with separate `CasterUnit` and `ArtilleryUnit` semantics;
   Arclight inherits artillery behavior and the future shared Mage inherits caster behavior.
4. Make Guardian/Ripper/Brute, Marksman/Spitter, and Arclight inherit the semantic behavior bases.
5. Remove `Knight`, `Archer`, and `Mage` from behavior exports until all three return as concrete
   content in S3.
6. Update docstrings and tests that still describe the legacy roster.
7. Prove runtime stats, attacks, poison, frenzy, shields, dead zones, and splash are unchanged.

### Exit criteria

- behavior-class names describe mechanics rather than historical content;
- no concrete faction unit inherits from another content unit;
- factory mappings and canonical content IDs are unchanged;
- deterministic replay digest is unchanged;
- full gate passes and the sprint is committed.

---

## 7. Sprint S2 — Multi-producer content contract

**Size:** M
**Goal:** allow one canonical unit definition to be trained by multiple faction buildings.

### Work

1. Replace singular `UnitDefinition.produced_at` with a typed tuple or remove it in favor of the
   reciprocal building `produces` graph. Prefer one authoritative graph, not two writable sources.
2. Update registry validation for missing producers, duplicate links, faction legality, and units
   with no producer.
3. Update `ProductionSystem.can_enqueue_unit`, command-panel queries, content guides, tests, and
   any observation metadata using the old singular producer.
4. Support shared units produced by faction-specific buildings without hardcoded content IDs.
5. Add table-driven tests for one producer, multiple producers, wrong-faction producers, missing
   links, and duplicate links.
6. Keep current units and production behavior exactly unchanged during this sprint.

### Exit criteria

- the production graph has one canonical source of truth;
- a test-only shared unit can be produced from two valid buildings;
- no production caller compares against one hardcoded `produced_at` value;
- current content, replay, and production timing remain unchanged;
- full gate passes and the sprint is committed.

---

## 8. Sprint S3 — Restore Knight, Archer, and Mage as shared content

**Size:** XL
**Goal:** add playable Knight, Archer, and tier-two Mage units to both factions without doctrines
yet.

### Work

1. Add canonical shared `knight`, `archer`, and `mage` definitions with `faction=None`.
2. Add concrete `Knight(MeleeUnit)`, `Archer(DeadZoneRangedUnit)`, and `Mage(CasterUnit)` classes.
3. Register all three IDs in `EntityFactory` and both faction rosters.
4. Add Knight and Archer to Arsenal/Pit, and Mage to Spire/Chem-Vat production lists.
5. Add English labels, command-panel entries, portraits, and team-specific sprites:
   `blue_knight.png`, `red_knight.png`, `blue_archer.png`, `red_archer.png`, `blue_mage.png`, and
   `red_mage.png`.
6. Keep baseline mechanics intentionally neutral: Knight is a dependable melee body; Archer has a
   readable ranged dead zone and melee fallback; Mage is a fragile medium-range caster using a
   basic magic attack until the ability system lands in S6.
7. Add map-schema acceptance, runtime-definition parity, asset-completeness, production, rally,
   combat, selection, and headless tests.
8. Do not add Knight, Archer, or Mage to existing competitive starting armies unless separately
   approved.

### Exit criteria

- both factions can train Knight and Archer from their tier-one producer and Mage from their
  tier-two producer;
- the units use shared content definitions but faction/team-specific visuals;
- existing advanced faction units retain their roles and stats;
- shipped maps remain compatible and symmetric where required;
- render smoke and full gate pass; sprint review is committed.

---

## 9. Sprint S4 — Canonical upgrade registry and team state

**Size:** L
**Goal:** introduce validated, pure, deterministic upgrade definitions without research UI yet.

### Target definitions

Add typed immutable structures equivalent to:

- `UpgradeDefinition`;
- `StatModifier`;
- `GrantedBehavior` or a closed typed ability key;
- `UpgradeId` and `ExclusivityGroupId`.

An upgrade definition includes:

- stable ID and English display name;
- owning faction;
- research building or valid research buildings;
- Wood/Gold cost and research frames;
- required buildings and prerequisite upgrades;
- exclusive group and conflicting upgrade IDs;
- affected unit/building content IDs;
- typed integer/fixed-point modifiers;
- optional closed behavior key.

### Work

1. Add upgrade definitions to `ContentRegistry` as a read-only index.
2. Validate IDs, faction ownership, research buildings, affected content, modifier fields,
   prerequisite cycles, and exclusivity consistency.
3. Add ordered completed-upgrade state to `TeamState` with pure query helpers.
4. Add an `UpgradeSystem` that computes effective stats from base definitions and completed IDs.
5. Recompute existing affected entities once on completion and apply derived values to new spawns.
6. Define and test max-life/max-shield, cooldown, attack-type, and current-state transition rules.
7. Ensure no upgrade scan occurs on an idle simulation tick.

### Exit criteria

- invalid tech graphs fail at registry construction;
- completing a test upgrade affects existing and future units identically;
- reapplying or iterating upgrades cannot stack modifiers accidentally;
- faction and exclusivity checks are deterministic;
- existing gameplay is unchanged when no upgrades are completed;
- full gate passes and the sprint is committed.

---

## 10. Sprint S5 — Research queue, cancellation, and core UI

**Size:** XL
**Goal:** make research a complete player action sharing a production building's activity queue.

### Work

1. Generalize the unit production queue into typed building activity jobs, or introduce an
   equivalent single-slot coordinator that prevents simultaneous training and research.
2. Preserve unit spawning, population reservation, refunds, and producer rally handoff.
3. Add `can_research`, `enqueue_research`, `cancel_research`, progress, and completion APIs.
4. Validate resources, faction, building requirements, prerequisite upgrades, exclusivity,
   duplicate research, building life, and construction state before payment.
5. Complete research through `UpgradeSystem` in deterministic building/entity order.
6. Add English command-panel buttons, disabled reasons, costs, queue progress, and cancellation.
7. Show completed and currently researching upgrades in selection details.
8. Add headless-safe public commands without modifying RL adapters, reward factories, or AI.
9. Add tests for mixed unit/research queues, cancellation refund, destroyed researcher, restart,
   simultaneous teams, and production rally after queue generalization.

### Exit criteria

- a building cannot train and research at the same time;
- cancellation and destruction have explicit tested resource behavior;
- research works identically with or without Pygame;
- unit production and rally regressions remain green;
- no RL or ScriptedAI file changes;
- full gate passes and the sprint is committed.

---

## 11. Sprint S6 — Deterministic caster energy and abilities

**Size:** XL
**Goal:** give shared Mage a pure, reusable caster model before faction-specific spells are added.

### Target definitions and state

Add typed immutable structures equivalent to:

- `AbilityDefinition` with stable ID and English display name;
- integer energy cost, cooldown frames, cast range, and optional duration;
- closed target kind (`self`, `ally`, `enemy`, `ground`, or bounded area);
- closed effect key interpreted by a focused ability system;
- faction/upgrade grant requirements;
- per-unit integer energy, maximum energy, regeneration accumulator, and cooldown state.

### Shared Mage baseline

- Mage remains fragile and medium-ranged rather than duplicating Arclight artillery.
- Its default magic attack works without research and without an active ability.
- Energy and cooldowns advance in simulation frames only.
- The baseline Mage has no faction-specific passive hidden behind team color.
- Missing energy, invalid targets, death, interruption, and target loss have explicit command
  results. Entity-target casts remain valid based on deterministic range/life/ownership rules after
  issue; presentation only permits the player to click entities it currently renders as visible.

### Work

1. Add ability definitions to the canonical content registry and validate IDs, grants, targets,
   ranges, energy, cooldowns, durations, and effect keys.
2. Add a focused `AbilitySystem` and a first-class `cast` order with stable target entity IDs or
   world destinations.
3. Define whether casting stops movement, can be Shift-queued, and how interruption/cancellation
   affects energy and cooldown; apply one contract consistently.
4. Regenerate energy with deterministic integer/fixed-point accumulation and no wall-clock time.
5. Add English command buttons, targeting mode, range/energy feedback, cooldown display, and safe
   disabled states.
6. Expose headless-safe cast commands without adding RL actions or changing rewards.
7. Add tests for queueing, interruption, energy boundaries, cooldown completion, invalid/dead
   targets, simultaneous casts, restart, target loss, and renderer independence.
8. Prove idle units with no active cooldown/energy work do not create an all-caster global scan.

### Exit criteria

- Mage has deterministic energy and a reusable ability command path;
- Arclight remains `ArtilleryUnit` and does not inherit Mage/caster state;
- abilities are definition-driven and Pygame-free in simulation;
- faction-specific Mage abilities can be added without new command infrastructure;
- full gate and benchmark pass; review accepted and committed.

---

## 12. Sprint S7 — AEGIS doctrine tree

**Size:** XL
**Goal:** make shared units express AEGIS precision, shields, formation play, and caster control.

### Knight choice at Arsenal

**Bulwark Doctrine**

- grants Knight a regenerating AEGIS shield;
- grants a hold-ground defensive behavior while stationary/holding;
- emphasizes protecting ranged units and maintaining a line;
- must not become a hidden global armor bonus unrelated to positioning.

**Vanguard Doctrine**

- grants a deterministic charge after sufficient uninterrupted movement;
- the first valid melee contact applies a bounded impact effect such as knockback or a brief
  simulation-frame stun;
- has less defensive persistence than Bulwark;
- charge state is explicit, observable in the game UI, and reset by clear deterministic events.

### Archer choice at Arsenal

**Longshot Doctrine**

- increases effective ranged reach and setup commitment;
- preserves or enlarges the dead zone so melee pressure remains a real counter;
- rewards protected firing positions rather than mobile kiting.

**Arcshot Doctrine**

- marks a target on a landed ranged hit for a bounded number of simulation frames;
- marked targets receive a deterministic AEGIS combined-arms interaction, such as improved
  focus-fire or Arclight targeting, defined centrally;
- has less raw reach than Longshot.

### Mage choice at Spire

**Shieldweaver Doctrine**

- grants `Barrier Pulse`, spending energy to restore a bounded amount of shield to nearby allied
  AEGIS units;
- never creates shields on units whose effective definition has no shield capacity;
- uses the spatial index, a capped target count, and stable `entity_id` application order;
- favors defensive formation play and competes with offensive control from Arcbinder.

**Arcbinder Doctrine**

- grants `Arc Bind`, spending energy to mark and temporarily slow one legal enemy target;
- the mark uses the same central combined-arms contract as Arcshot/Arc Targeting;
- effect duration and movement restoration are deterministic and survive neither death nor restart;
- favors setup for Marksman and Arclight rather than shield sustain.

### Advanced Spire research

- `Shield Network`: improves a bounded subset of AEGIS shield interactions without modifying RUST
  or shared unresearched units.
- `Arc Targeting`: strengthens the explicit mark/Arclight synergy without adding renderer-owned
  targeting state.

### Work and exit criteria

1. Implement each behavior through closed upgrade/ability keys and focused systems.
2. Add mutual-exclusion tests for all three AEGIS doctrine groups.
3. Add tests for shields, hold state, charge reset, dead-zone behavior, mark expiration, splash
   interaction, Barrier Pulse target caps, Arc Bind cleanup, energy/cooldowns, existing/future
   units, and deterministic replay.
4. Add a second golden technology replay covering at least one AEGIS doctrine path and Mage cast.
5. Confirm that choosing one doctrine creates a meaningful tactical loss of the alternative.
6. Full gate and benchmark pass; review accepted and committed.

---

## 13. Sprint S8 — RUST doctrine tree

**Size:** XL
**Goal:** make shared units express RUST swarm, frenzy, mobility, poison pressure, and mutation.

### Knight choice at Pit

**Frenzy Doctrine**

- grants a bounded low-health attack-speed behavior using the existing deterministic frenzy model;
- may restore a small bounded amount of life on a confirmed kill if the mechanic is accepted in S0;
- rewards continuous combat and damaged-unit aggression;
- cannot trigger from allied deaths or renderer events.

**Pack Doctrine**

- grants Knight a bonus based on nearby living allied melee units;
- uses the spatial index and a capped contributor count;
- recomputes from local deterministic state rather than maintaining an unbounded aura graph;
- remains weak when isolated and distinct from Ripper's raw speed.

### Archer choice at Pit

**Venom Doctrine**

- grants a bounded poison application through the existing `apply_damage`/effects path;
- refresh/stack rules are explicit and reuse the canonical poison contract;
- prioritizes attrition against durable AEGIS targets.

**Skirmisher Doctrine**

- improves movement-to-fire responsiveness through deterministic frame rules;
- favors repositioning and harassment rather than poison strength;
- does not implement unrestricted firing while moving unless separately approved and tested.

### Mage choice at Chem-Vat

**Plaguecaller Doctrine**

- grants `Toxic Cloud`, spending energy on a bounded ground area that applies the canonical poison
  or a typed combat debuff in stable entity order;
- does not stack unbounded overlapping clouds or allocate permanent area objects;
- emphasizes enemy attrition and area denial.

**Mutagenist Doctrine**

- grants `Mutagenic Surge`, spending energy to temporarily strengthen a capped set of nearby RUST
  melee units through the canonical frenzy/pack modifier path;
- cannot affect enemies, buildings, dead units, or AEGIS content;
- emphasizes an allied swarm timing window and sacrifices Plaguecaller's area pressure.

### Advanced Chem-Vat research

- `Advanced Mutations`: strengthens a bounded frenzy/pack interaction across selected RUST units.
- `Concentrated Toxins`: strengthens poison duration or cadence through the central effect rules.

### Work and exit criteria

1. Implement all mechanics through the same registry and upgrade systems as AEGIS.
2. Add mutual-exclusion tests for all three RUST doctrine groups.
3. Add spatial-boundary, contributor-cap, poison refresh, low-health threshold, kill attribution,
   Toxic Cloud overlap/cleanup, Mutagenic Surge target caps, energy/cooldowns, existing/future unit,
   and replay tests.
4. Extend the technology replay with at least one RUST doctrine path, Mage cast, and cross-faction
   combat.
5. Prove RUST doctrine logic does not scan every unit globally each tick.
6. Full gate and benchmark pass; review accepted and committed.

---

## 14. Sprint S9 — Tech-tree UI, documentation, and stage closure

**Size:** L
**Goal:** make the complete technology system readable, playable, and protected for the next stage.

### Work

1. Add an English faction tech-tree view generated from registry dependencies, not a duplicated UI
   graph.
2. Show buildings, trained units, research, requirements, completed state, active progress, costs,
   exclusive choices, granted abilities, Mage energy, and cooldowns.
3. Use clear visual states for available, locked, researching, completed, and excluded upgrades.
4. Ensure the tree remains readable at supported window sizes and does not mutate simulation state.
5. Add concise tooltips/descriptions for doctrine behavior and exclusivity consequences.
6. Update README, architecture, content authoring, controls, and determinism documentation.
7. Add a guide for defining upgrades and doctrine groups in one canonical place.
8. Add a guide for defining abilities, targeting contracts, and temporary effects without adding
   Pygame or content-ID conditionals to simulation.
9. Validate every shipped faction tree for reachability, cycles, orphan upgrades, producer legality,
   and at least one valid path through each exclusivity group.
10. Run long-match and 400-unit benchmarks with completed upgrades and active Mage effects.
11. Mark this plan COMPLETE with actual commits, final test count, replay digests, and measurements.

### Exit criteria

- a player can understand and execute both faction trees without reading source code;
- UI dependencies are derived from `ContentRegistry`;
- headless simulation remains independent of Pygame and the tech-tree view;
- both faction trees have executable validation and deterministic replay coverage;
- no known upgrade stacking, queue, exclusivity, ability, temporary-effect, spawn, or restart defect
  remains;
- full CI/benchmark gate passes and the closure review is committed.

---

## 15. Sprint dependency and commit map

| Sprint | Depends on | Primary risk | Expected commit theme |
|---|---|---|---|
| S0 | current game core | ambiguous doctrine semantics | `docs: define expanded tech tree contracts` |
| S1 | S0 | combat regression during rename | `refactor: separate combat behaviors from content` |
| S2 | S1 | duplicated producer truth | `refactor: support canonical multi-producer units` |
| S3 | S2 | roster/asset integration | `feat: restore shared knight archer and mage units` |
| S4 | S3 | modifier stacking or nondeterminism | `feat: add deterministic upgrade registry` |
| S5 | S4 | production/research queue regression | `feat: add building research activities` |
| S6 | S5 | caster state/action complexity | `feat: add deterministic caster abilities` |
| S7 | S6 | AEGIS ability edge cases | `feat: add aegis doctrine tree` |
| S8 | S7 | RUST aura/poison performance | `feat: add rust doctrine tree` |
| S9 | S8 | UI duplication and incomplete docs | `feat: complete faction tech tree experience` |

No sprint starts with a dirty worktree from the previous sprint. A failed review is fixed within the
same sprint and commit; it is not carried forward as known debt.

---

## 16. Definition of Done

Executive Plan 06 is complete only when:

- semantic behavior bases replace legacy content-named base classes;
- Knight, Archer, and Mage are real shared, producible, rendered units for both factions;
- the content graph supports multiple producers with one authoritative definition path;
- upgrades and research have immutable validated definitions;
- team-wide modifiers affect existing and future entities identically;
- production and research have one explicit building-activity contract;
- Mage energy, cooldowns, cast orders, and abilities are deterministic and presentation-independent;
- all six doctrine groups enforce mutual exclusion atomically;
- AEGIS and RUST have mechanically distinct Knight, Archer, and Mage play styles;
- advanced faction units retain unique roles;
- tech-tree UI is derived from the registry and uses English game text;
- deterministic technology replay, full tests, maps, render smoke, CI, and benchmarks pass;
- ScriptedAI, automated balance, rewards, environment lifecycle, and RL adapters remain untouched.

After acceptance, Executive Plan 07 may cover AI strategy, automated balance evaluation, RL action
and observation integration, reward design, multi-environment lifecycle, and self-play.

---

## 17. Main risks and controls

| Risk | Control |
|---|---|
| Shared units dilute faction identity | Strong mutually exclusive doctrines and advanced faction alternatives |
| Behavior rename changes combat | S1 is refactor-only with unchanged replay digest |
| Multi-producer graph duplicates truth | One authoritative producer graph with reciprocal validation derived from it |
| Upgrades stack repeatedly | Recompute effective stats from immutable base definitions |
| Research breaks production/rally | One typed building activity contract and spawn-handoff regression tests |
| Exclusive upgrades both enter queues | Validate and reserve exclusivity atomically before payment |
| Aura/pack logic regresses performance | Spatial queries, capped contributors, benchmark before/after |
| Mage abilities expand state/action complexity | One typed energy/cooldown/cast contract before faction spells |
| Area effects retain unbounded objects | Bounded durations, stable targets, explicit cleanup, long-run tests |
| UI becomes another tech registry | Generate nodes and edges from `ContentRegistry` only |
| Balance work blocks architecture | Use provisional centralized values; defer numeric tuning to Plan 07 |
| RL APIs churn prematurely | Do not modify env, rewards, AI, or RL adapters in this plan |
