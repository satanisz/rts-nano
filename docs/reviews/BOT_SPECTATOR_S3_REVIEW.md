# Bot Spectator S3 — Acceptance and Delivery

Date: 2026-10-29. Status: complete.

The spectator mode is composed through typed launch options and the application match controller.
The observer has All/Blue/Red views, read-only inspection, both teams' statistics, camera/minimap,
pause, speed, technology overview, fullscreen, neutral results, and deterministic restart.
Launch and controls: [Watching bot matches](../BOT_SPECTATOR.md).
Design and sprint scope: [Plan 09](../../EXECUTIVE_PLAN_09_BOT_SPECTATOR.md).

## Ownership and regression protection

- `MatchController` owns participants, stable Blue→Red decisions, pause/result guards, and fresh
  restart. `main.py` retains SDL/display/event composition. Quit now exits before another game tick.
- `MatchView` owns presentation visibility and inspection; the bot's own vision/memory remains
  private. The observer input path blocks gameplay keys/clicks before command dispatch.
- Existing game rules, simulation runner, definitions, and ML-facing interfaces are unchanged.
  The new mode uses the current baseline bots, including their limited strategy.
- A 4,000-tick test compares real rendered/interactive observation against equivalent headless
  decisions, checking gameplay checkpoints and both bots' knowledge. Only UI team/selection fields
  are excluded from that comparison. A real main-loop test covers pause, restart, and immediate quit.

## Acceptance-discovered performance issue

The baseline bot repeatedly searched the same unreachable scout route on Twin Rivers. A late-match
profile spent 8.24 of 8.31 seconds in scouting decisions, including six redundant route searches
over 85 simulated ticks. This cost existed in the baseline AI and was exposed by running both sides.

S3 adds **one failed ground-scout request** per bot. Reuse requires the same scout, origin, radius,
destination, order/queue, terrain geometry, and building obstacle revision; an entity entering the
clicked point forces another attempt. It preserves the chosen scout/goal and does not add a route,
new tactic, or additional information to the bot's knowledge. There is no unbounded retry history.

Nine regression cases verify identical gameplay against uncached retries and invalidation after
goal, origin, scout, building, terrain, entity target, order, and queue changes. Twenty identical
failed decisions now use one path search. Restart also clears the request cache.

The retained [before-cache reference](assets/bot-spectator/baseline-before-cache.json) includes two
complete Crown Divide matches and one complete Twin Rivers match. All its recorded gameplay/bot
knowledge checkpoints agree with optimized runs. Twin Rivers took 1,013.089 s in that reference
and approximately 24 s in the optimized runs. These local timings include other verification
activity and are not an isolated hardware benchmark or a fixed-frame-rate guarantee.

## Whole-match evidence

`benchmarks/bot_spectator.py` runs real bots from original zero-bank starts through the ordinary
36,000-tick rules, with no injected economy, army, damage, or deadline jump. It records combat,
both armies, checkpoints every 6,000 ticks and at result, then verifies a fresh two-bot restart.
Checkpoints include canonical gameplay fields plus each bot's decision count, vision grid, and
remembered enemy base. UI team/selection fields are excluded.

| Map | Both repetitions | Result tick | Landed attacks per run | Local elapsed seconds |
|---|---|---:|---:|---|
| Crown Divide | Red wins by elimination | 11,726 | 359 | 6.293 / 6.612 |
| Twin Rivers | Draw at the ordinary deadline | 36,000 | 264 | 23.880 / 24.366 |
| Ashen Circuit | Draw at the ordinary deadline | 36,000 | 293 | 159.677 / 172.542 |

All six runs demonstrate production by both sides, combat, a bounded result, and fresh restart.
The three paired runs agree at **14 gameplay/bot-knowledge checkpoints**. In total, they advance
167,452 ticks. Raw evidence: [acceptance.json](assets/bot-spectator/acceptance.json).
Default starts are Blue AEGIS / Red RUST. The outcomes describe these baseline bot matches, not
competitive balance or simultaneous combat fairness.

## Visual inspection

`benchmarks/bot_spectator_visuals.py` uses real bot development at tick 4,000, actual observer
keyboard/mouse events, a naturally resolved Crown Divide match, and the real restart path.
It injects no funds, units, research, damage, or tick jumps. Frames were generated with dummy SDL
and inspected as images; this was not a human desktop playtest.

| Frame | Observation |
|---|---|
| [All](assets/bot-spectator/01-all.png) | Unobscured world/minimap; separate team statistics, mode, clock, speed, and observer help. |
| [Blue](assets/bot-spectator/02-blue.png) | Blue visibility and explored terrain; unknown map/minimap regions hidden. |
| [Red](assets/bot-spectator/03-red.png) | Independent Red perspective after actual minimap navigation. |
| [Inspection](assets/bot-spectator/04-inspection.png) | Enemy Pit HP and training visible with observer help replacing gameplay cards. |
| [Technology](assets/bot-spectator/05-technology.png) | RUST research overview displays a read-only instruction. |
| [Menu/speed](assets/bot-spectator/06-menu-speed.png) | Working menu actions, fast speed, and restored explicit pause; no unsupported Save/Load items. |
| [Result](assets/bot-spectator/07-result.png) | Neutral RED WINS, reason, restart/quit; result replaces still-open F9. |
| [Restart](assets/bot-spectator/08-restart.png) | All view, zero banks/time, fresh participants and normal speed. |
| [Compact](assets/bot-spectator/09-compact.png) | HUD/minimap/help fit the supported 640×360 window. |

The other frames use 1280×720. Inspection led to a dark HUD background and width-adjusted stat
fonts, improving readability over units/terrain and at the minimum window size.

## Final validation

| Check | Result |
|---|---|
| Full pytest and statement/branch coverage | **417 passed**, 97.92 s; **79.08%**, above the required 50% |
| Ruff check / format | PASS; **128 Python files** formatted |
| Ty | PASS for application and both acceptance helpers |
| Shipped maps | **6/6 PASS**, v2 and v3 |
| Existing three replay suites, separate process with hash seed 1 | **6/6 PASS** |
| Same suites, separate process with hash seed 97 | **6/6 PASS** |
| Real two-bot full matches and restart | **6/6 PASS**, 14 repeated checkpoint comparisons |
| Original versus optimized full-match checkpoints | PASS for every retained Crown/Twin reference checkpoint |
| Rendered observer versus headless behavior | PASS through 4,000 ticks including UI interaction |
| Visual inspection | Nine frames inspected, 1280×720 and 640×360 |

The suite increases from 385 to 417 cases: S1 adds seven, S2 fourteen, S3 eleven. Tests also keep
application/headless imports free of Pygame. CI's dummy-SDL render job now explicitly includes
spectator input/render parity and startup tests; remote GitHub execution was not observed locally.

The final full suite followed the scouting optimization and HUD/text adjustments. A first full
before-cache Twin reference was deliberately retained; the remaining redundant unoptimized runs
were stopped after its complete evidence was saved. The post-cache six-run acceptance completed.

README changes use verified manifest/lockfile requirements, startup parser/help, input handling,
tests, and workflows. The updated launch flags were checked with the local interpreter and the
main-loop integration test; a fresh dependency installation was not repeated. Internal document
links were checked locally. No README placeholders or unverified badges were added.

Reproduce using the existing `.venv` executables, or equivalent commands after locked `uv` setup:

```text
python -m rts_nano.main --help
python -m pytest --basetemp=tmp/pytest-spectator-final --cov=src/rts_nano
ruff check .
ruff format --check .
ty check src/rts_nano
python benchmarks/bot_spectator.py --repeats 2 --output tmp/bot-spectator.json
```

The guide contains dummy-SDL visual regeneration commands. In PowerShell, expand shipped JSON map
paths with `Get-ChildItem` and pass those explicit paths to `python -m rts_nano.validate_map`.
Three stored golden replay files remain unchanged. No new training, balance, bot-capability,
networking, or ML API scope is introduced. Existing expensive paths may still produce slow frames.
