# Game Stage Closeout Audit

Date: 2026-10-28. Commit: `8e06cd5d1ba0eaea5a2171285d9321b1dcd727ab`.
Scope: rules, economy, combat, input, maps, determinism, tests, performance, and documentation.
**Preparing an ML API is excluded.**

## Verdict

**The technical foundation is reusable, but the whole game stage should not yet be marked
complete.** No new factions, units, or architectural rewrite are needed. Three rule fixes,
a match-ending decision, and acceptance of existing gameplay remain.

Plan 05's `GAME CORE READY` is the historical result of its architecture migration. It does not
prove that the subsequently expanded game has no bugs. `env.py`, actions, and rewards already
exist; further development of those layers is not required by this audit or implicitly commissioned.

Verified rules: [GAME_RULES](../GAME_RULES.md).
Concrete acceptance criteria: [Plan 08](../../EXECUTIVE_PLAN_08_GAME_STAGE_CLOSEOUT.md).
This audit changed documentation only; **G1–G3 were not fixed in the audited revision**.

## Existing capabilities worth retaining

| Area | Repository evidence | Assessment |
|---|---|---|
| One rendered/headless core | SimulationRunner, GameSession, HeadlessSimulation; import-boundary and presentation-parity tests | Retain; do not build a second simulation for RL |
| Central definitions and object identity | content/registry.py, EntityStore; registry, faction, stable-ID tests | Implemented and suitable for freezing content |
| Economy, construction, repair, FIFO, rally | Headless, strategic-action, research-queue tests | Implemented, with G1/G3 defects |
| Combat, statuses, technology tree | AEGIS/RUST, ability, upgrade, technology replay tests | Implemented; not proof of complete balance |
| Navigation and dynamic obstacles | Core hardening, pathfinding, terrain, safe spawning | Implemented; longer active matches need broader acceptance |
| Three v3 maps | Validation, symmetry/routes/economy tests, Red bot vs idle Blue | Mechanically playable; symmetry does not prove faction balance |
| Result and restart | Victory, episode lifecycle, match-result tests | Elimination and restart work; game stalemate policy remains open |
| Deterministic replays | Three golden replays; additional processes with distinct hash seeds | Confirmed for the tested scenarios/current runtime |
| Content-authoring guides | Architecture, adding content, map authoring, tech-tree authoring | Maintain; small documentation discrepancies are recorded below |

## Confirmed defects

### G1 / P1 — Population cost disappears between queue and army

Location: [`production.py`](../../src/rts_nano/game/production.py), `can_enqueue_unit`, lines 109–110;
[`state.py`](../../src/rts_nano/game/state.py), `count_units`, lines 116–118. The HUD in `renderer.py`
also shows unit count next to population capacity.

The code adds the **number** of existing units to the **population cost** of queued units.
Executed example: one Peasant and three Arclights occupy 10 population with a Base providing 10.
`count_units` returns 4 and `can_enqueue_unit(spire, "arclight")` returns `(True, None)`.
Another unit is allowed despite full supply. In an ordinary two-bot Crown Divide match,
AEGIS finished with 15 population against a capacity of 10, a living Base, and no House.

Impact: broken economy and uneven unintended advantages across factions and units costing 1/2/3.
A later agent could learn to exploit the cap bug. Fix production, reservation consistency, and HUD
semantics; increasing supply or adjusting balance does not address the cause.

### G2 / P1 — Right-click bypasses fog of war

Location: [`input_controller.py`](../../src/rts_nano/game/ui/input_controller.py),
`_handle_right_click`, lines 302–305; a similar unfiltered cast-target lookup occurs at line 249.
`GameSession.select_units_in_box` filters visibility, making the input paths inconsistent.

Executed reproduction: a Red Base at `(1400, 400)`, Blue near `(80, 80)`, and refreshed Blue fog
reporting `visible=False`, `explored=False`. Right-clicking the hidden Base with a worker selected
assigns that Base to `target_entity` and records an `attack` order. Prior sighting is not required.
Cast lookup also has no visibility filter; that conclusion comes from code inspection, not a
separate executed cast reproduction.

Impact: player input knows objects the renderer hides. The technology contract already requires
rendered/selectable targets; fixing this does not require a new advanced vision system. Check every
object-targeting path, including resources, rally, and casts, and document tracking after visibility
is lost following a legal selection.

### G3 / P2 — Dead workers contribute construction work

Location: [`construction.py`](../../src/rts_nano/game/construction.py), `_builders_for_team` and
`update` (lines 61 and 144). Work aggregation does not filter worker HP. The runner removes dead
entities only after construction updates.

Executed controlled reproduction: a worker in `BUILDING`, assigned to a House with 100 build ticks
remaining, receives `life=0` before a simulation step. After one `GameSession.update()`, the House
has 99 ticks remaining and the worker is removed. This isolates system ordering; it does not measure
how frequently the bug occurs in combat. The same path aggregates repair work and needs an analogous
regression test.

Impact: death does not immediately stop work, especially on a building's completion tick.
Acceptance must also cover workers killed by an enemy earlier in the same tick.

## Decisions and acceptance gaps, separate from defects

**D1 — Match endings.** `VictorySystem` counts all living units/buildings, without detecting an
inability to fight. Two opposing Houses still give `result=None`, `paused=False` after 36,001 ticks.
This follows current elimination rules rather than proving the function is broken. Decide how
such matches end before closeout. Plan 08 recommends elimination plus a limit and draw. Until then,
claiming every match ends would be incorrect.

**D2 — Bot scope and balance.** `ScriptedAI` does not expand its economy with workers/Houses,
research doctrines, or cast spells. Existing full-match v3 tests run Red against idle Blue.
That is a valid smoke test, not acceptance of two developing sides or the whole content set.
A stronger bot is unnecessary; controlled scenarios and a brief visual acceptance suffice.
Basic balance deserves attention after G1, but competitive 50/50 is not a requirement.

**D3 — Coverage and performance.** Player-input coverage is about 35%, renderer coverage 45%.
These figures do not independently block completion, but help explain why core-only tests missed G2.
CI runs benchmark smoke without enforcing timing thresholds. Historical reports give review budgets,
not an automated regression gate. Active v3 matches and memory under load need acceptance; 5,000 idle
ticks do not provide that evidence.

**D4 — Project boundaries.** Non-constructable Bases, no terrain vision occlusion, a simple bot,
a limited editor, and no campaign can remain explicit limitations. RL does not automatically require
these additional features.

## Verification results at audit time

Local environment: Windows, Python 3.14.4, pytest 9.0.2, existing `.venv`. Initially clean working
tree. Remote CI status and other operating systems were not checked.

| Check | Result |
|---|---|
| Full pytest with coverage | **325 passed**, 73.89 s; test-order seed 788170428 |
| Combined statement/branch coverage | **74.86%**; repository threshold 50% |
| Ruff format / Ruff check / ty | PASS; 113 correctly formatted files |
| All v2/v3 JSON maps | **6/6 PASS** |
| Core + technology + joint replays, hash seed 1 | **6/6 PASS** |
| Same replays, separate process, hash seed 97 | **6/6 PASS** |
| Render smoke and parity | PASS in full pytest; not a manual playtest |
| Targeted G1/G2/G3/D1 probes | Confirmed as described above |

`uv run pytest` completed the suite. Subsequent `uv` commands encountered a sandbox denial writing
its interpreter cache. Static checks, map validation, benchmarks, and additional processes used the
existing `.venv` executables directly. This was a tool-launch limitation, not a gameplay defect.

### Extended benchmark

Command: `.venv/Scripts/python.exe benchmarks/core_baseline.py --extended --repeats 3 --scenario-steps 200`.
Local-machine medians without coverage; not a guarantee for other hardware.

| Scenario | Ticks/s | S5 review budget |
|---|---:|---:|
| Idle legacy map 01 | 8882.020 | >= 6000 |
| Active economy | 3804.719 | >= 2500 |
| 80-unit combat | 561.546 | >= 350 |
| 400 dispersed units | 87.074 | >= 60 |
| 400 close-combat units | 36.840 | >= 25 |

Idle initialization: 2.417 ms (<20 ms). Two 400-unit group orders: 2284.865 ms (<5000 ms).
Retained Python memory after 5,000 idle ticks: 0.000 MiB at report precision. These samples satisfy
historical review budgets. 36.84 ticks/s does not imply 60 FPS or high future training throughput;
400 units is a stress workload.

### Additional two-bot matches

Two `ScriptedAI` instances, default decision interval, Blue → Red → one game tick. Observation
budget: 12,000 ticks, stopping on a natural result. Ordinary map starts without extra resources.
Each case ran once without coverage.

| Map | Blue / Red | Final measured tick | Result | Wall time |
|---|---|---:|---|---:|
| Crown Divide | AEGIS / RUST | 9911 | Blue wins | 7.767 s |
| Twin Rivers | AEGIS / RUST | 12000 | no result within budget | 117.521 s |
| Ashen Circuit | AEGIS / RUST | 12000 | no result within budget | 43.252 s |
| Crown Divide | RUST / AEGIS | 11868 | Red wins | 36.184 s |

No result at 12,000 ticks does not prove an infinite stalemate. These probes justify broader
endgame acceptance, not faction-strength conclusions. On Twin Rivers, Blue lost its Base but kept
an Arsenal and units; on Ashen Circuit, both sides lost all buildings but retained units. Current
rules correctly withheld a result in those states. Timing differences require profiling if they
exceed an agreed active-match budget; these measurements alone do not identify a bottleneck.

## Documentation updated during the audit

- Added [GAME_RULES](../GAME_RULES.md): implemented state, limitations, and known bugs.
- Added [Plan 08](../../EXECUTIVE_PLAN_08_GAME_STAGE_CLOSEOUT.md): C1 integrity, C2 visibility,
  C3 endings, C4 acceptance and version freeze.
- Added architecture links and updated `MEMORY.md` navigation.
- Corrected queue/effect descriptions in `TECH_TREE_CONTRACTS.md`: cancellation removes the first
  entry, not any index; research emits no separate completion event; statuses use counters rather
  than a generic expiry/source-ID registry.
- Replaced the historical “boundary before runtime implementation” statement in
  `RL_ENVIRONMENT_CONTRACT.md` with an implemented-code description. This corrects documentation
  without expanding scope into ML API preparation.

## Short G1–G3 reproduction

Save the following code under `tmp/` and run it with the project interpreter. These are diagnostic
probes of the audited behavior, not acceptance tests preserving bugs. Expected values must change
after fixes.

```python
import os

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import pygame
from rts_nano.application import GameSession
from rts_nano.game.entity_factory import EntityFactory
from rts_nano.game.ui.input_controller import InputController
from rts_nano.simulation.entities import TeamColor


def settings():
    return {
        "schema_version": 2,
        "Blue": {"faction_id": "AEGIS", "base": [[80, 80]], "peasant": [[120, 80]]},
        "Red": {"faction_id": "RUST", "base": [[1400, 400]]},
        "Resources": {"wood": [], "gold": []},
        "Terrain": {"width": 1600, "height": 900, "water": [], "rocks": [],
                    "ramps": [], "high_ground": [], "grass": []},
    }


# G1: actual population 10/10; another Arclight is incorrectly allowed.
data = settings()
data["Blue"].update(arclight=[[250, 100], [330, 100], [410, 100]], spire=[[80, 250]])
game = GameSession(data)
game.teams[TeamColor.BLUE].resources.update(wood=1000, gold=1000)
producer = game.state.entities_by_content_id("spire", team=TeamColor.BLUE)[0]
print(sum(u.definition.population for u in game.units_for_team(TeamColor.BLUE)))  # 10
print(game.production.can_enqueue_unit(producer, "arclight"))  # (True, None)

# G2: a hidden base is targeted through player right-click input.
pygame.init()
game = GameSession(settings())
game.fog.update(game.state.entities_for_team(TeamColor.BLUE))
target = game.bases_for_team(TeamColor.RED)[0]
worker = game.units_for_team(TeamColor.BLUE)[0]
game.selected_entities = [worker]
InputController()._handle_right_click(game, (1400, 400))
print(game.fog.is_visible(*target.get_center()), worker.target_entity is target)  # False True
pygame.quit()

# G3: a dead worker contributes before end-of-tick cleanup.
game = GameSession(settings())
worker = game.units_for_team(TeamColor.BLUE)[0]
building = EntityFactory.create("house", 180, 80, TeamColor.BLUE)
building.start_construction(100)
game.state.add_runtime_entity(building)
worker.target_entity, worker.state, worker.life = building, "BUILDING", 0
game.update()
print(building.construction_remaining_frames, worker in game.all_entities)  # 99 False

# D1: both sides have only a house and no units capable of ending the match.
data = settings()
data["Blue"] = {"faction_id": "AEGIS", "house": [[80, 80]]}
data["Red"] = {"faction_id": "RUST", "house": [[1400, 400]]}
game = GameSession(data)
for _ in range(36001):
    game.update()
print(game.state.tick_count, game.game_over_message, game.paused)  # 36001 None False

```

## Limits of confidence

This audit does not prove the absence of all bugs. It did not execute the complete same-faction
matrix on every map, a long active leak test, or manual UI acceptance. It did not assess ML adapters,
observation schemas, reward quality, training, or learnability. The verdict is a solid core with a
bounded game-closeout backlog, not a ready training environment.
