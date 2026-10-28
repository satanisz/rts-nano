# Plan 09 — Bot Match Spectator

Date: 2026-10-29. Status: implementation in progress.

## User outcome

Add a windowed mode for watching two existing scripted bots play. The default human-versus-Red-bot
mode remains available. Launch with `python -m rts_nano.main --mode spectate`; `--map` continues to
select a packaged or explicit map. Repository documentation and code remain English.

The observer can inspect living objects, navigate the camera/minimap, pause, adjust speed through
the existing menu, open F9, restart, and quit. Tab cycles All / Blue / Red visibility. The observer
cannot issue unit, economy, research, construction, spell, queue, or rally commands.

## Architecture decisions

1. An application-level match controller owns the game session, mode, and participating bots.
   `main.py` composes it and owns the SDL loop. The simulation runner remains the only rules engine.
2. Play runs the Red bot; Spectate runs Blue then Red before each simulation tick. Both inspect the
   same pre-tick world. Submission order is stable, not a guarantee of simultaneous resolution or
   competitive fairness. Pausing/ending prevents bot decisions as well as simulation advancement.
3. A separate presentation view owns spectator visibility and exploration. All-map visibility
   changes drawing and inspection only. It never reveals terrain or enemies to a bot's own memory.
   Blue/Red perspective grids refresh while spectating, including when another view is selected.
4. Read-only input is enforced before gameplay dispatch. Spectator inspection does not reuse a
   player command path. Production command cards are replaced with observer controls/help.
5. Restart creates a fresh session and fresh bots, retaining mode, map, match rules, and display
   configuration. Observer view/transient UI state resets. Completed results use neutral team labels.
6. One composition path serves all maps/factions. No second simulation, stronger strategy bot,
   replay system, auto-camera, networking, training code, or ML API is part of this change.

## S1 — Match orchestration and launch configuration

Status: complete — [S1 review](docs/reviews/BOT_SPECTATOR_S1_REVIEW.md).

- Add typed Play/Spectate mode and application match ownership.
- Move participant creation, ordered decisions, pause/end guards, and restart out of `main.py`.
- Add CLI mode selection with Play as the default; keep display behavior and map resolution.
- Verify real bot activity, stable decision order, pause/end guards, fresh restart, startup options,
  and imports without Pygame. Commit the coherent application change.

## S2 — Observer presentation and read-only controls

Status: pending.

- Add isolated All/Blue/Red observation policy and per-team presentation exploration.
- Share the policy between world drawing, effects, minimap, and inspection.
- Gate gameplay input at dispatch; allow inspection, camera/minimap, pause/menu/speed, F9, restart,
  fullscreen, and quit. Replace command cards with help; show both teams' economy and population.
- Show team-neutral results, including when F9 is open. Reset presentation with a restarted match.
- Test actual keyboard/mouse/card/rally attempts, perspective visibility, and bot knowledge isolation.
  Commit the complete observer interaction layer.

## S3 — Acceptance and documentation

Status: pending.

- Run each shipped v3 map through the two-bot application controller to a bounded result; restart.
- Compare fresh runs and a rendered observer against equivalent headless decisions. Exercise view
  changes/inspection during replay to prove they cannot alter gameplay or bot knowledge.
- Inspect actual rendered observer views: All/Blue/Red, selection, HUD, menu/speed, result, restart.
- Run full pytest/coverage, static checks, six-map validation, and unchanged golden replay gates.
- Document launch/controls, architecture, tests, known baseline-bot limits, and measured acceptance.
  Record a separate completion commit and provide the launch command.

## Acceptance limits

The baseline bot gathers, builds one basic producer, trains, scouts, and attacks. It does not build
Houses, train additional workers, research, or cast abilities. Spectating exposes its current
behavior; improving that strategy requires a separate scope decision. A time-limit Draw is a valid
result under the frozen game rules. Rendering throughput is not training throughput.
