# Watching Bot Matches

The spectator mode runs the existing baseline bot on both Blue and Red. Its rules, content, and
36,000-tick match deadline are the same as the playable game. Spectator input can inspect the
match and control its presentation; unit and economy commands are disabled.

## Launch

From the repository root after `uv sync --locked --dev`:

```powershell
uv run python -m rts_nano.main --mode spectate
uv run python -m rts_nano.main --mode spectate --map map_spec_02.json
```

With the existing Windows virtual environment, the equivalent command is:

```powershell
.venv/Scripts/python.exe -m rts_nano.main --mode spectate
```

The default command without `--mode`, or with `--mode play`, starts the original playable mode.
`--map` accepts packaged map names or explicit JSON paths. The spectator window title is
`RTS Nano - Bot Spectator`.

## Controls

| Control | Effect |
|---|---|
| Tab | Cycle All → Blue → Red → All terrain/object visibility |
| Left-click an object | Inspect either team's visible object, including HP, work, and production |
| Click/drag the minimap | Move the camera |
| Arrow keys / WASD / screen edges | Pan the camera |
| P or Space | Pause/resume bot decisions and simulation |
| F10 | Open/close the pause menu; select normal / fast / slow speed (1x / 2x / 0.5x) |
| F9 | Open/close the current view team's technology overview; All uses Blue |
| Escape | Close the technology overlay or menu; otherwise clear inspection |
| R | Restart the same map with fresh game state and two fresh bots |
| F11 / Alt+Enter | Toggle fullscreen |
| Q / window close | Quit |

The HUD always shows both teams' banks, weighted population/capacity, queued population, and
building counts, plus the clock and speed. All view reveals the map to the observer. Blue/Red
views filter terrain and objects using separate presentation exploration grids; match-wide HUD
statistics remain visible. These views do not alter a bot's own vision, exploration, or enemy memory.

Right-click, production/research cards, construction, spells, queue cancellation, unit orders, and
control groups cannot command either army while spectating. Observer help replaces gameplay cards.
Closing the observer menu restores the prior pause choice. Restart resets the perspective to All,
clears inspection/exploration, and returns speed to normal through the existing session reset.

Results use neutral BLUE WINS / RED WINS / DRAW labels. Restart and quit controls take precedence
over an open technology overlay. Match termination uses ordinary elimination or the game deadline;
a computer running slowly may take longer than ten wall-clock minutes to advance all 36,000 ticks.

## Bot and determinism limits

The baseline bot gathers, builds one basic military producer, trains soldiers, scouts, and attacks.
It does not build Houses, train additional workers, research doctrines, or use spells. Both bots
submit decisions in stable Blue→Red order before each simulation tick. This mode does not establish
simultaneous combat resolution, competitive fairness, or faction balance.

The bot retains one failed ground-scouting request to avoid repeatedly searching an unchanged
unreachable route. Its chosen scout and destination stay the same. Changes to the scout, position,
radius, order/queue, target occupancy, terrain, or building revision cause a retry. Restart clears
that request along with the bot's vision and enemy memory.

Behavior is deterministic for the same map/rules and ordered commands on the supported runtime.
Camera position, view changes, inspection, and rendering do not affect gameplay. Pause freezes
ticks; speed changes the pacing of those ticks. Expensive baseline pathfinding can cause slow frames;
the observer mode does not improve the bot strategy or guarantee a fixed frame rate.

## Implementation and acceptance

The Pygame-free `application/MatchController` owns participants and restart. Presentation owns
`MatchView`; the existing `GameSession`/`SimulationRunner` owns rules. The observer is a local
application mode and introduces no ML interface.

See [Plan 09](../EXECUTIVE_PLAN_09_BOT_SPECTATOR.md),
[architecture](../ARCHITECTURE.md), and the [acceptance review](reviews/BOT_SPECTATOR_S3_REVIEW.md).

Reproduce full two-bot matches and compare checkpoints with bot knowledge included:

```powershell
.venv/Scripts/python.exe benchmarks/bot_spectator.py --repeats 2 --output tmp/bot-spectator.json
```

Regenerate the visual acceptance views:

```powershell
$env:SDL_VIDEODRIVER='dummy'
$env:SDL_AUDIODRIVER='dummy'
.venv/Scripts/python.exe benchmarks/bot_spectator_visuals.py
```
