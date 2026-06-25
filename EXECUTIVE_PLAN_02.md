# RTS Nano - Executive Plan 02

Last updated: 2026-06-26

This document supersedes EXECUTIVE_PLAN.md for sprint tracking and current state.
The original document remains as architectural reference. This one reflects the
repository state after the Gold rename commit and contains an updated gap analysis
and prioritized next-work list.

---

## 1. Product Goal (unchanged)

RTS Nano should become a fully functional RTS game comparable to WarCraft II at
the gameplay mechanics level — economy, production, construction, combat, unit
orders, victory conditions, a playable human UI, and a stable RL training API.

The second core goal is a deterministic headless simulation environment for
training neural networks at scale.

---

## 2. Hard Design Rules (unchanged)

1. Gameplay before animation.
2. Simulation must run without Pygame, images, or a window.
3. Lightweight: scales to many parallel instances.
4. Deterministic: same seed + map + actions = same result.
5. API-first: every mechanic reachable through typed action/observation contracts.
6. Small verified steps: each stage ends with green headless tests.

---

## 3. Confirmed Repository State as of 2026-06-26

All 18 tasks from EXECUTIVE_PLAN.md section 10 are complete. Confirmed green:
`ruff`, `ty`, `pytest`, `tox`, `pre-commit`. The Cristal resource has been fully
renamed to Gold (sprite, portrait, entity class, data keys, observations, tests).

### What Works Right Now

**Units (4 types, all functional):**
- Peasant — gathers wood/gold, deposits, builds Barracks/House
- Knight — melee combat
- Archer — ranged combat with dead-zone fallback
- Mage — defined in data, producible at Mage Tower (but Mage Tower not yet buildable)

**Buildings (3 of 5 are constructible in-game):**
- Base — peasant production, resource dropoff, 10 population
- Barracks — knight/archer production, constructible by peasant
- House — population +6, constructible by peasant
- Mage Tower — data and production queue defined, but not constructible in ConstructionSystem
- Defense Tower — data defined, not buildable at all

**Economy and Production:**
- Wood and gold gathering and deposit cycle
- Queued unit production with time, cost, cancellation, and partial refund
- Population cap from completed support buildings
- Cost denial messages with compact missing-resource display

**Orders (14 action types, all implemented):**
- NoOp, Move, Attack, AttackMove, Gather, Deposit, ReturnCargo
- Build (queue unit), Construct (place building), CancelConstruction, CancelProduction
- Stop, Hold, Select
- Hotkeys: S/H/A/G/C/B/Y

**Infrastructure:**
- Grid A* pathfinding with terrain-aware predicates
- Fog of War with UNEXPLORED/EXPLORED/VISIBLE states
- Serializable observation snapshots with stable entity IDs across episode
- `RtsNanoEnv`: reset, step, observe, available_actions, action_mask, reward, close
- Headless simulation wrapper (no window, no Pygame surface)
- 7 test modules covering environment, headless, production, construction, pathfinding, terrain, map schema

---

## 4. Gap Analysis — What Is Missing for the Full Game

### 4.1 Building Roster Is Incomplete

**Mage Tower (missing from ConstructionSystem):**
- `BuildingSpec` and `UnitSpec` for mage exist in `data.py`
- `ProductionSystem` handles mage production queue
- `ConstructionSystem` does not list "mage_tower" as a buildable type
- Map schema and editor do not place Mage Towers
- No UI button or hotkey for peasant to construct Mage Tower

**Defense Tower (not implemented):**
- `BuildingSpec` in `data.py` defines cost and footprint
- No entity class, no map spawn, no construction, no attack behavior
- Towers need an attack system different from units (stationary, auto-only, range priority)

### 4.2 Victory Conditions — Not Implemented

The game has no defined win state. `game_over` in observations is always None.
The Definition of Done requires explicit victory conditions. The most natural
approach for WarCraft II parity is base elimination: a team loses when all their
Bases are destroyed. A secondary timeout/scenario rule is useful for training.

Missing pieces:
- `VictorySystem` or equivalent check in the tick loop
- `game_over` field in `Observation` populated correctly
- Reward signal on terminal state in `RtsNanoEnv`
- Tests for terminal episode detection

### 4.3 Order Model — Scattered Flags

Unit behavior is currently tracked through individual fields on unit objects:
`state`, `target_entity`, `attack_move_destination`, `source_resource`. There is
no formal `Order` or `Command` object. This makes priority handling implicit and
hard to test.

Needed:
- A small `Order` dataclass (kind, target, destination, metadata)
- Units hold a current `order: Order | None`
- Order priority: manual > auto-attack > return-to-work
- Clear behavior when a target dies mid-order

Missing orders:
- Patrol (unit moves between two waypoints, attacking on sight)
- Follow/Guard (unit trails a target entity)
- Repair (peasant repairs a damaged building)

### 4.4 Combat Gaps

Current combat works for basic use cases but is not complete:
- No fog-aware targeting: units can acquire and attack enemies outside visible area
- No armor/damage type system (piercing vs normal vs siege — relevant for WarCraft II parity)
- Attack cooldown exists but is not consistently tested headless
- Projectile damage is applied correctly but the projectile system is Pygame-coupled
- No explicit target-death cleanup in all order states (some edge cases exist)

### 4.5 GameManager Decomposition (architectural debt)

`GameManager` still owns: entity state, tick logic for gathering, combat,
production, construction, projectiles, fog, camera, HUD, minimap, selection, and
victory. The plan targets decomposing this into a `Simulation` core + Pygame
adapter. This is not blocking any single feature but creates risk as the codebase
grows.

No urgent blocker today, but the recommended approach is: extract one system per
sprint, starting with `VictorySystem` and `CombatSystem` since those are the most
self-contained.

### 4.6 Training API Gaps

- No formal observation schema version number
- `reward()` in `RtsNanoEnv` is a stub (returns 0 by default); no domain reward functions
- No headless steps/sec benchmark
- No batch episode runner
- Observation does not expose fog state, last-seen tile map, or spatial grid

### 4.7 Human UI Gaps

- Command panel only has buttons for the current selected unit — no production queue progress display
- No population progress display in HUD (shows total but no near-cap warning)
- No Mage Tower or Defense Tower buttons
- Minimap clicks do not issue camera-move commands
- No unit grouping (Ctrl+1..9 control groups)

### 4.8 Maps and Scenarios

- Three maps exist but none have configured victory conditions or resource balance tuned for testing
- No scripted AI opponent
- No small training scenarios (harvest, rush, defend)

---

## 5. Prioritized Sprint Plan

Sprints are ordered by impact on reaching the Definition of Done. Each sprint
ends with green tests and a playable headless check.

### Sprint 1 — Complete Building Roster + Victory Conditions

**Goal:** close the last major gameplay loop gaps so the game has a real end state.

Tasks:
1. Add Mage Tower to `ConstructionSystem` (copy Barracks pattern, add "mage_tower" key)
2. Add Mage Tower entity class with sprite/portrait hook matching the Gold pattern
3. Add Mage Tower build button and hotkey for Peasant in the command panel
4. Add map schema and map editor support for Mage Tower
5. Add `VictorySystem`: team loses when all Bases are destroyed; set `game_over` in observations
6. Wire victory detection into `RtsNanoEnv.step` — mark episode as done, return terminal reward
7. Add tests: mage tower construction headless, mage production headless, victory condition headless

Defense Tower can follow immediately after or in Sprint 2 since it requires a
stationary attack system that does not exist yet.

**Exit criteria:** headless test shows a team can construct Mage Tower, queue a
mage, and the game correctly terminates when a base is destroyed.

---

### Sprint 2 — Formal Order Model

**Goal:** replace scattered unit flags with a typed `Order` object; add Patrol.

Tasks:
1. Define `Order` dataclass with `kind`, `target_id`, `destination`, and metadata
2. Each unit stores `current_order: Order | None`
3. Migrate existing order application in `manager.py` and `orders.py` to set `current_order`
4. Define clear priority: manual order > auto-attack > return-to-work
5. Handle target death: units in ATTACKING clear their order when target dies
6. Add `PatrolAction` DTO, add to `OrderSystem`, add command panel button and hotkey `P`
7. Update observation snapshot to expose `current_order.kind` per entity
8. Update action mask to include patrol legality
9. Tests: patrol coverage headless, target-death cleanup headless, deterministic replay with patrol

**Exit criteria:** units can patrol between two waypoints, stop when given a manual
order, resume patrol when stopped, and the order state is visible in observations.

---

### Sprint 3 — Defense Tower + Combat Improvements

**Goal:** complete the building roster and harden combat for RL.

Tasks:
1. Add `Tower` entity class (building subclass with auto-attack-only behavior)
2. Add Tower to `ConstructionSystem`
3. Add Tower build button for Peasant
4. Fix fog-aware targeting: units and towers should only auto-acquire targets visible
   to their team's fog grid
5. Add damage type field to `UnitSpec` / `BuildingSpec` (normal / piercing / siege) and
   armor field to entities; apply multipliers in `rules.py`
6. Extract combat tick from `GameManager` into `CombatSystem` (stateless system, takes
   entity list and fog grid, returns damage events)
7. Tests: tower auto-attack headless, fog-aware targeting headless, damage type application

**Exit criteria:** a tower placed on high ground attacks enemy units that enter its
range and have visible fog state; damage types apply correct multipliers.

---

### Sprint 4 — Training API + Benchmarks

**Goal:** agents get complete, versioned, cheap observations and a real reward signal.

Tasks:
1. Add observation schema version field to `Observation`
2. Add domain reward functions to `env.py`: resources_gathered, units_killed, buildings_destroyed,
   game_won; configurable weights in `RtsNanoEnv` constructor
3. Add fog state exposure in `Observation` (per-tile visibility as flat array or encoded)
4. Write headless steps/sec benchmark script in `benchmarks/` (no window, no assets, pure sim)
5. Profile and document the bottlenecks (pathfinding, observation serialization, fog update)
6. Add batch episode runner: reset N envs, run K steps each, collect total reward
7. Update `action_mask` to cover all new Sprint 1-3 actions (mage tower, tower, patrol)

**Exit criteria:** benchmark prints steps/sec for 1 and 8 parallel headless instances;
a sample reward script runs one episode and returns a non-zero score.

---

### Sprint 5 — GameManager Decomposition

**Goal:** reduce `GameManager` to a Pygame adapter; simulation logic lives in systems.

This sprint is architectural, not feature-adding. No new visible gameplay.

Tasks:
1. Extract `VictorySystem` (already done in Sprint 1 but as a module — decouple it from manager)
2. Extract `GatherSystem`: harvesting tick, carry logic, source replacement
3. Extract `CombatSystem`: already started in Sprint 3 — finish full extraction
4. Define `GameState` dataclass holding entity lists, team resources, fog grid, tick counter
5. `GameManager` calls `Simulation.tick(game_state, events)` rather than owning all logic
6. Headless wrapper uses `Simulation` directly, not `GameManager`
7. All existing tests must still pass

**Exit criteria:** `HeadlessSimulation` does not import any Pygame symbols; `GameManager`
contains only rendering, input, camera, and HUD code.

---

### Sprint 6 — Human UI Completion

**Goal:** a human can play a full skirmish session without missing UI.

Tasks:
1. Production queue progress bars in command panel for selected building
2. Population near-cap warning in HUD
3. Mage Tower and Defense Tower construction buttons and hotkeys
4. Minimap click scrolls camera to location
5. Patrol/Follow buttons in command panel
6. Repair button for Peasant when adjacent to damaged building
7. Control groups: Ctrl+1-9 assign, 1-9 recall
8. Double-click to select all visible units of same type

---

### Sprint 7 — Maps, Scenarios, and Scripted AI

**Goal:** the game has content for both playing and training.

Tasks:
1. Tune map_settings_01/02/03 with explicit victory conditions and resource placement
2. Add a fourth map designed for 1v1 fast skirmish training
3. Implement a scripted AI: gather → build barracks → train knights → attack base
4. Add small training scenarios: harvest-only, rush-attack, base-defense
5. Add map metadata: player_count, start_positions, resource_density, victory_rule
6. First balance pass on costs and unit stats

---

## 6. Definition of Done (unchanged from original)

The game is considered functionally complete when:

- A human can play a skirmish locally against another human or the scripted AI
- The game ends through explicit victory conditions
- Workers gather resources, construct buildings, and return to work
- Buildings produce units through queues with costs and time
- Units support the standard RTS command set including patrol
- Combat, movement, fog, and economy work in headless simulation
- `RtsNanoEnv` lets an agent reset, step, observe, read action masks, rewards, and done state
- Simulation runs without a window and without rendering
- Steps/sec benchmarks and deterministic tests exist
- `ruff`, `ty`, `pytest`, `tox`, and `pre-commit` pass

---

## 7. Immediate Next Task

Start Sprint 1, task 1: add Mage Tower to `ConstructionSystem`.

The pattern is already established for Barracks in `construction.py`. The key
change is registering `"mage_tower"` in the construction lookup alongside the
`MageTower` entity class (to be created under `game/assets/entities/buildings.py`
matching the existing `Barracks` class shape).

---

## 8. Risks

| Risk | Control |
|------|---------|
| `GameManager` keeps growing | Every Sprint 1-3 system gets its own module; Sprint 5 enforces the boundary |
| Pygame leaks into RL API | Headless tests ban any Pygame import; enforced by CI |
| Observation cost grows with entity count | Benchmark before Sprint 5; spatial index if justified |
| Victory detection creates false terminals | Cover all terminal states in headless tests with explicit sequences |
| Order model refactor breaks deterministic replay | Keep replay test and run it after Sprint 2 migration |

---

## 9. Rules for Future Sessions

- Read this file before writing any code.
- Check `git status` before changes.
- Add a headless test for every gameplay change.
- Commit small; do not mix building roster, order model, and architecture in one commit.
- Update this file or EXECUTIVE_PLAN.md when sprint status changes.
- Do not add PyTorch, Gymnasium, or PettingZoo to core; use optional adapters.
