# RTS Nano - Executive Plan 03

Last updated: 2026-06-27

This document continues EXECUTIVE_PLAN_02.md. That plan delivered the gameplay
feature set (Sprints 1–7), a profile-driven performance pass, and a collision
correctness pass. This plan is **single-purpose**: finish the `GameManager`
decomposition that Sprint 5 (in plan 02) deliberately left partial.

It exists because of a concrete verdict: the cross-entity *rules* are now in
systems, but `GameManager` is still a ~1640-line god object doing four unrelated
jobs at once. This document turns that verdict into a prioritized, low-risk work
order.

---

## 1. Why this plan exists (the verdict)

Measured state of [manager.py](src/rts_nano/game/manager.py) on 2026-06-27:

- **1972 lines total**; the `GameManager` class is ~1640 of them across ~85 methods.
- Largest single methods: `draw_bottom_menu` **~222 lines**, `handle_input`
  **~196 lines**, `draw` **~134 lines**, `update` ~73 lines.

`GameManager` currently mixes four responsibilities in one class:

1. **Rendering** (~500+ lines of pygame): `draw`, `draw_bottom_menu`,
   `draw_minimap`, `draw_main_menu`, `_draw_pending_construction`, `_format_cost`.
2. **Input** (~300 lines): `handle_input`, menu clicks, camera control, the
   construction-placement and unit-command targeting modes.
3. **Simulation movement/combat logic** still living in the manager:
   `_update_attack_move_target`, `_resume_or_finish_attack_move`, `_update_patrol`,
   `_nearest_attack_move_target`, `_formation_destinations`, `_assign_unit_target`,
   `_assign_group_move_order`, `_update_unit_stuck_recovery`.
4. **Simulation ownership / tick orchestration**: entity rosters, `update`,
   height refresh, population, map loading.

### What is already good (do not undo)

The cross-entity rules are extracted into real systems and should stay there:
`OrderSystem`, `ProductionSystem`, `ConstructionSystem`, `CombatSystem`,
`GatherSystem`, `VictorySystem`. Headless runs deterministically; 78 tests pass.
This plan does not touch gameplay rules — only structure.

### The core architectural smell

- **Render ↔ input coupling through button rects.** `draw_bottom_menu` both draws
  the command panel *and* appends hit-target rectangles to `self.production_buttons`,
  `self.construction_buttons`, `self.cancel_*_buttons`, `self.unit_command_buttons`,
  which `handle_input` then reads on the next click. So input hit-testing depends on
  the draw pass having run. This must be untangled before render and input can split
  cleanly.
- **System → manager back-coupling.** Systems reach back into the manager
  (`self._manager.entities`, `self._manager._assign_unit_target`, …). There is no
  `GameState` container; the manager *is* the shared state. This is the deepest knot
  and is addressed last.

---

## 2. Hard design rules (carried over, still binding)

1. **Gameplay/behavior is frozen.** This is a structural refactor. No rule, cost,
   timing, or order semantics may change. Unit positions, combat outcomes, and
   observation contents must stay identical.
2. **Determinism.** Same seed + map + actions ⇒ identical snapshots. The
   deterministic replay tests are the guard rail and must stay green after every step.
3. **Simulation without renderer dependency.** The end state must let the core run
   with no pygame draw/font/event calls. Headless tests must never require a display
   surface.
4. **Public API compatibility.** `RtsNanoEnv`, `HeadlessSimulation`, the action DTOs,
   and observations must keep working unchanged. `GameManager`'s public order helpers
   may stay as thin delegators for compatibility.
5. **Small verified steps.** One component extracted per sprint, full gate green
   (`ruff`, `ruff format`, `ty`, `pytest`) after each. No mixing of two extractions in
   one commit.
6. **Move, don't rewrite.** Prefer relocating existing code verbatim into a new
   collaborator over re-implementing it. Behavior-preserving moves keep the diff
   reviewable and determinism intact.

---

## 3. Target architecture

The three-layer split the original plan called for, made concrete for this codebase:

```
Presentation (pygame)          Input (pygame)            Core simulation (no pygame draw/event)
  GameRenderer                   InputController            GameManager  -> thin coordinator
  - draws map/entities/HUD       - translates events       - owns GameState + systems
  - draws minimap/menu             into action DTOs /       - runs the tick
  CommandPanel (shared)            manager calls            MovementSystem
  - computes commands + rects    - camera, menu,            - attack-move/patrol/formation/stuck
    (pure logic, headless-safe)    placement/targeting      GameState
                                                            - entity rosters, resources, fog, tick
```

`GameManager` shrinks to a coordinator: build `GameState`, own the systems, expose
the public order/query API, and run `update()` by delegating to systems. Rendering
and input become adapters that read/command it. Nothing in the core calls
`pygame.draw`, `pygame.font`, or inspects `pygame.event`.

---

## 4. Work plan (prioritized by value / risk)

Ordered so the biggest, lowest-risk line reductions and the worst coupling come
first; the deepest change (`GameState`) comes last.

### Sprint A — Extract `CommandPanel` (untangle render ↔ input)

**Goal:** make the command-panel layout a pure, testable component so render and
input stop sharing it implicitly.

Tasks:
1. New `CommandPanel` (e.g. `game/ui/command_panel.py`) that, given the current
   selection + team economy, returns the list of available commands — label,
   enabled state, action key, cost hint — and their screen rects, with **no
   drawing**. This is the logic currently inside `draw_bottom_menu`.
2. `draw_bottom_menu` becomes: ask `CommandPanel` for the commands/rects, then only
   draw them. `handle_input` asks `CommandPanel` for the same rects to hit-test,
   instead of reading draw-populated `*_buttons` lists.
3. Tests: headless test that `CommandPanel` returns the right commands for a
   peasant (build buttons), a base (train/cancel), and a unit selection
   (stop/hold/patrol/gather/return-cargo) with correct enabled/denied reasons.

**Exit criteria:** the `self.*_buttons` lists are no longer populated by drawing;
both render and input read `CommandPanel`. Gate green.

### Sprint B — Extract `GameRenderer`

**Goal:** remove all rendering from `GameManager`.

Tasks:
1. New `GameRenderer` taking the manager (read-only) + `CommandPanel`. Move `draw`,
   `draw_bottom_menu`, `draw_minimap`, `draw_main_menu`, `_draw_pending_construction`,
   and `_format_cost` into it, plus projectile/marker drawing.
2. `main.py` calls `renderer.draw(screen, manager)` instead of `manager.draw(screen)`.
3. Keep world↔screen transforms where both render and input need them (shared helper
   or on the camera; do not duplicate silently).
4. Confirm no `pygame.draw`/`pygame.font` symbol remains referenced in `manager.py`.

**Exit criteria:** `GameManager` has zero drawing methods; the windowed app still
renders (manual smoke check) and headless is unaffected. Gate green.

### Sprint C — Extract `InputController`

**Goal:** remove event/input handling from `GameManager`.

Tasks:
1. New `InputController` owning `handle_input`, `_handle_menu_click`,
   `_set_menu_option`, camera input (`_update_camera`), and the placement/targeting
   modes (`begin_*`, `place_pending_construction`, `cancel_pending_*`,
   `select_units_in_box`, control-group keys, double-click).
2. Where practical, input translates to the **same action DTOs** agents use, so the
   human and the agent share one path. Where that is too invasive now, call the
   manager's public order helpers directly and note it.
3. `main.py` routes events to `InputController`.

**Exit criteria:** `GameManager` contains no `pygame.event`/key handling; the app is
still playable (manual smoke check). Gate green.

### Sprint D — Extract `MovementSystem`

**Goal:** move the remaining simulation movement logic out of the manager.

Tasks:
1. New `MovementSystem` owning `_update_attack_move_target`,
   `_resume_or_finish_attack_move`, `_update_patrol`, `_nearest_attack_move_target`,
   `_formation_destinations`, `_assign_unit_target`, `_assign_group_move_order`,
   `_update_unit_stuck_recovery`, `_can_unit_move_to`, `_find_unit_path`.
2. `GameManager.update` and `OrderSystem` call into `MovementSystem`.
3. Deterministic replay test must stay byte-identical (this sprint is the highest
   determinism risk because it touches the movement tick).

**Exit criteria:** movement/pathing logic lives in `MovementSystem`; replay tests
identical. Gate green.

### Sprint E — Introduce `GameState`

**Goal:** give systems an explicit state object so they stop reaching through the
manager.

Tasks:
1. Define `GameState` holding entity rosters/groups, neutral resources, fog, tick
   counter, current team, and `game_over`.
2. Systems take `GameState` (not `GameManager`) for their reads/writes.
3. `GameManager` becomes a thin coordinator over `GameState` + systems; the public
   API delegates.
4. `HeadlessSimulation` drives `GameState`/systems; assess whether it can finally
   drop its pygame import (stretch goal — units still use pygame time helpers).

**Exit criteria:** systems no longer reference `GameManager`; `GameManager` is a
coordinator. Gate green; replay tests identical.

---

## 5. Definition of Done (for the decomposition)

- `GameManager` contains **no** `pygame.draw`/`pygame.font` calls and **no**
  `pygame.event` handling; it is a coordinator under ~400 lines.
- Rendering lives in `GameRenderer`; input in `InputController`; the command panel
  layout in a shared `CommandPanel`; movement in `MovementSystem`; shared state in
  `GameState`.
- Systems depend on `GameState`, not on `GameManager`.
- Public API (`RtsNanoEnv`, `HeadlessSimulation`, actions, observations) unchanged.
- Deterministic replay tests produce identical snapshots before and after each sprint.
- `ruff`, `ruff format`, `ty`, `pytest` all green; gameplay behavior unchanged.

---

## 6. Risks and controls

| Risk | Control |
|------|---------|
| A behavior-changing refactor breaks determinism | Run the replay tests after every sprint; treat any snapshot diff as a regression, not a rebaseline. |
| Render ↔ input button-rect coupling causes subtle UI breakage | Sprint A extracts `CommandPanel` first; nothing else moves until render and input read the same source. |
| World↔screen transforms get duplicated/diverge | Keep one shared transform (camera or a small helper) used by both render and input. |
| Movement extraction (Sprint D) shifts unit positions | Move code verbatim; do not "improve" it during the move; compare replay snapshots. |
| `GameState` becomes a second god object | `GameState` holds data only; behavior stays in systems. |
| Scope creep into gameplay changes | This plan is structure-only. Any new feature/balance goes back to plan 02's deferred list, not here. |

## 7. Sequencing note

A → B → C are mostly mechanical relocations with low determinism risk (presentation
and input do not affect the simulation tick). D and E touch the tick and shared
state and carry the real determinism risk; do them last, one at a time, with the
replay tests watched closely. Each sprint is independently shippable — the plan can
stop after any sprint with the suite green.

## 8. Out of scope (tracked elsewhere)

Carried-forward gameplay/content follow-ups stay in EXECUTIVE_PLAN_02.md and are not
part of this decomposition: Follow/Repair orders, production progress bars, shared
per-team fog memory, a richer damage-type/armor matrix, map metadata, dedicated
training maps, and the balance pass.
