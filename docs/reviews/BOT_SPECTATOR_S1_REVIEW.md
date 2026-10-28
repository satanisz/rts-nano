# Bot Spectator S1 — Application Match Ownership

Date: 2026-10-29. Status: complete.

`MatchController` owns the session, typed Play/Spectate mode, and bot instances. Play composes the
existing Red opponent. Spectate composes Blue then Red; both decide before one shared simulation
tick. Pause and terminal state prevent all further bot decisions. Restart creates fresh bots and
session state while retaining participant mode and the existing map/rules/display reset contract.

`main.py` now delegates participant lifecycle and stepping to that controller. Typed launch options
accept `--mode play|spectate` alongside the existing `--map`. No simulation, bot strategy, content,
or ML interface was modified. Read-only observer presentation follows in S2.

Validation: **21 targeted tests passed** across startup, controller lifecycle, real two-bot
development, architecture boundaries, and existing bot behavior. The real bot test starts both
sides with the original zero bank and verifies producers and soldiers after 4,000 ticks. Separate
process checks keep application/headless imports free of Pygame. Ruff, format, and ty pass.
