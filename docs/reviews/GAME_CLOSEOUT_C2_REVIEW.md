# Game Closeout C2 — Player Visibility

Date: 2026-10-28. Status: complete. Audit bug G2 is fixed.

Selection, right-click, gather, rally, and entity-cast input now resolve objects through the shared
GameSession player-target rule. Living allies are targetable, enemies must be visible, and resources
must be explored and nonempty. Unknown targets resolve as ground where supported and do not leak
object IDs. Target resolution refreshes sight independently of rendering.

Each selectable side retains separate exploration memory, and restart clears it. Dead allies grant
no sight; losing sight of a selected enemy clears inspection. Input and rendering use the same
refresh method. These are player-information fixes, not a new ML observation layer.

Accepted tracking policy: an attack or entity cast legally issued while the target is visible
continues to track it after sight is lost. An enemy rally stores only the observed position.
Ground/area spells remain coordinate-targeted and do not require an identified enemy object.

## Validation

- 30 new tests exercise real mouse/key/command-card paths for visible, explored-but-hidden,
  and never-explored targets, plus rediscovery, team switching, selection cleanup, and restart.
- Targeted input/presentation suite: 42 passed.
- Full suite: **363 passed**, coverage **76.85%**. Golden replays unchanged.
- Ruff, formatting, type checks, all six maps, and benchmark smoke pass.

Reproduce: `.venv/Scripts/python.exe -m pytest --basetemp=tmp/pytest-c2 --cov=src/rts_nano`.
Remaining closeout: match-ending rules (C3) and whole-game acceptance (C4).
