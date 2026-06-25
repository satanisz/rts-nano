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

### Sprint 1 — Complete Building Roster + Victory Conditions — DONE (2026-06-26)

**Goal:** close the last major gameplay loop gaps so the game has a real end state.

Tasks:
1. ✅ Add Mage Tower to `ConstructionSystem` (registered in `_BUILDING_FACTORIES` + `_BUILDING_ROSTERS`)
2. ✅ Add `MageTower` entity class in `buildings.py` with `spec_key = "mage_tower"`
3. ✅ Mage Tower build button (auto from `supported_building_types()`) + Peasant hotkey `M`
4. ✅ Map schema (`mage_tower` in `TeamSettings` + validator) and map editor (`Z`/`C` tools) support
5. ✅ Victory conditions: **already existed** via `GameManager._update_game_over_state` (team
   eliminated when all its entities are dead → last team standing wins / draw). Wired into the
   tick loop and exposed via `Observation.game_over` and `RtsNanoEnv.is_done()`.
6. ✅ `RtsNanoEnv.step` returns `done=True` on terminal state (already wired through `is_done`).
7. ✅ Tests: `test_worker_constructs_mage_tower_and_trains_mage` (headless),
   `test_env_action_mask_exposes_mage_tower_construction`, `test_env_reports_game_over_when_one_team_remains`,
   plus `mage_tower` added to the canonical map-schema payload test.

**Note on victory model:** the existing implementation uses **total elimination** (all units AND
buildings dead), not base-only elimination as the plan originally proposed. This is a valid
WC2-style condition and is left as-is; a base-only or configurable rule can be revisited in Sprint 7
balance work if endless-game edge cases appear.

Defense Tower deferred to Sprint 3 (needs a stationary attack system that does not exist yet).

**Exit criteria:** ✅ headless test shows a team can construct a Mage Tower, queue and spawn a
mage, and the env reports a terminal win when a rival team is eliminated. Full gate green:
ruff, ruff format, ty, 53 pytest passing.

---

### Sprint 2 — Formal Order Model — DONE (2026-06-26)

**Goal:** replace scattered unit flags with a typed `Order` object; add Patrol.

Tasks:
1. ✅ Defined `Order` dataclass (`kind`, `destination`) in new `game/order.py`.
2. ✅ Every unit stores `current_order: Order | None` (additive field on `Unit`).
3. ✅ Order helpers in `orders.py` tag `current_order` via `_tag_order`; `manager.py`
   helpers delegate unchanged.
4. ✅ Manual orders override patrol: `_tag_order` clears `patrol_points` for every
   non-patrol order, so a manual command unambiguously cancels an active patrol.
5. ✅ Target death already handled by the existing `Unit.update` (clears dead targets);
   patrol resumes its route afterward via the attack-move resume path.
6. ✅ `PatrolAction` DTO + `OrderSystem.issue_patrol_order` + `ActionTranslator` +
   manager helper + command-panel **Patrol** button + hotkey **`T`** (see deviation).
7. ✅ Observation `EntitySnapshot.order` exposes `current_order.kind`.
8. ✅ Action mask includes a `patrol` spec (enabled when the team has units).
9. ✅ Tests: patrol oscillation, stop-cancels-patrol, patrol acquires hostile (headless);
   env patrol action sets order + mask; deterministic patrol replay.

**Design deviations from the plan (intentional):**
- **Additive, not a rewrite.** The low-level state machine (`state`, `target_entity`,
  `path`, `attack_move_destination`, `source_resource`) remains the execution mechanism.
  `Order` is a descriptive layer set by the order helpers — this keeps determinism and
  all existing tests green (hard rule #6, small verified steps). A full flag-removal
  refactor is deferred to Sprint 5 (GameManager/Simulation decomposition).
- **Hotkey `T`, not `P`.** `P` is already bound to pause in the game client. Patrol uses
  `T`; the command-panel button is the primary discoverable path.
- **Patrol reuses attack-move acquisition.** A patrol leg sets `attack_move_destination`,
  so units acquire hostiles en route for free; `_update_patrol` flips to the farther
  waypoint when a leg completes.

**Exit criteria:** ✅ units patrol between two waypoints, divert to hostiles encountered
en route and resume, stop when given a manual order, and expose `order == "patrol"` in
observations. Full gate green: ruff, ruff format, ty, 58 pytest passing.

---

### Sprint 3 — Defense Tower + Combat Improvements — DONE (2026-06-26)

**Goal:** complete the building roster and harden combat for RL.

Tasks:
1. ✅ `Tower` entity (`Building` subclass) with ranged combat stats and an
   auto-attack-only profile (damage 12, range 180, no movement, no production).
2. ✅ Tower registered in `ConstructionSystem` (and the full roster ripple: factory,
   `EntitiesGroup.towers`, `all_entities`, dead-entity cleanup, schema, editor, counts).
3. ✅ Tower build button appears for Peasants automatically from
   `supported_building_types()`.
4. ◑ Fog-aware targeting (partial, by design): tower acquisition is limited to the
   tower's own attack reach, and unit attack-move acquisition is already limited to
   `vision_range`. This is per-acquirer line of sight — the practical equivalent of
   "only shoot what you can see." A **shared per-team fog grid** for targeting is
   deferred: today `GameManager.fog` is a single grid computed for `current_team`
   only, so true team-memory targeting needs the per-team fog work scheduled in
   Sprint 4 (fog exposure) / Sprint 5 (decomposition).
5. ◑ Damage types / armor (deferred): the existing model already provides damage
   typing via `AttackType` (melee/ranged, with height modifiers) and armor via
   `shield_modifier` in `calculate_damage`. A richer normal/piercing/siege-vs-armor-
   class matrix is a balance change deferred to Sprint 7 rather than adding a parallel
   half-system that could destabilize tested combat.
6. ✅ New `game/combat.py` `CombatSystem` owns stationary (tower) attacks: it applies
   deterministic damage and returns shot descriptions that `GameManager` renders as
   ranged projectiles. Unit combat intentionally still lives in `Unit.update`; this
   establishes the extraction pattern that Sprint 5 finishes without destabilizing the
   working unit combat path.
7. ✅ Tests: tower auto-attacks enemy in range, tower silent while under construction,
   tower ignores out-of-range enemy (headless); env action mask exposes tower construct.

**Design deviations (intentional):** items 4 and 5 are partially delivered with clear
follow-ups rather than rushed full systems — consistent with the "don't destabilize a
working solution" and "small verified steps" rules. The concrete, tested gameplay win
this sprint is a working defensive Tower plus a clean `CombatSystem` seam.

**Exit criteria:** ✅ a constructed tower attacks enemy units that enter its range,
stays inert while unfinished, and ignores enemies beyond range. Full gate green:
ruff, ruff format, ty, 62 pytest passing.

---

### Sprint 4 — Training API + Benchmarks — DONE (2026-06-26)

**Goal:** agents get complete, versioned, cheap observations and a real reward signal.

Tasks:
1. ✅ `Observation.schema_version` (module constant `OBSERVATION_SCHEMA_VERSION = 1`),
   serialized in `to_dict()`.
2. ✅ Reward library `rts_nano/rewards.py`: `win_loss_reward`, `resource_gain_reward`
   (step delta), `enemy_losses_reward` (step delta), and `combine` for weighted sums.
   These plug into the existing injectable `RtsNanoEnv(reward_fn=...)` — that injection
   point is the configurable-weights mechanism (no constructor change needed), keeping
   the env API stable and the game rules untouched.
3. ✅ Per-team fog exposure via `RtsNanoEnv.fog_state(team)` — builds a fresh `FogOfWar`
   from the team's entities and returns an immutable row-major grid (0/1/2). Kept off the
   default observation so many-instance training stays cheap (opt-in, not per-tick).
4. ✅ `rts_nano/benchmark.py` `measure_steps_per_second` + `benchmarks/headless_steps.py`
   CLI (no window, no draw).
5. ✅ Baseline recorded: ~840 steps/sec single instance on the full default map
   (`map_settings_01`), ~15k steps/sec on a tiny map. Dominant costs are per-tick entity
   iteration and pathfinding; spatial-index work stays deferred until entity counts justify
   it (consistent with the performance section).
6. ✅ `run_batch(num_envs, steps, ...)` advances many envs in one process and returns
   per-env reward totals; terminal envs stop accruing (no mid-run reset/close, so the
   shared headless pygame state stays valid for all instances).
7. ✅ Action mask already covers mage_tower/tower/patrol (added in Sprints 1–3).

**Tests:** rewards library (`test_rewards.py`), benchmark + batch + fog
(`test_benchmark.py`), and observation schema version (`test_env.py`).

**Note:** full per-team fog *memory* (shared explored grid persisted across ticks per team)
is still deferred to Sprint 5; `fog_state` recomputes current visibility on demand, which
is sufficient for a fog-limited observation today.

**Exit criteria:** ✅ the benchmark reports steps/sec for one instance and `run_batch`
returns per-env rewards (a forced win returns a non-zero terminal score). Full gate green:
ruff, ruff format, ty, 71 pytest passing.

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

Sprints 1–4 are complete. Start Sprint 5: GameManager decomposition.

This is an architectural sprint with no new visible gameplay. Extract self-
contained tick logic out of `GameManager` into systems (start with the gather
tick, since combat already has a `CombatSystem` seam and victory is isolated in
`_update_game_over_state`). Keep every existing test green and preserve
determinism — extract one system at a time and run the full suite after each.

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
