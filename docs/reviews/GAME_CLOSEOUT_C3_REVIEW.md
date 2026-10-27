# Game Closeout C3 — Bounded Matches

Date: 2026-10-28. Status: complete.

Ordinary game sessions now use immutable `MatchRules`, defaulting to 36,000 simulation ticks
(10 nominal minutes). Elimination of all opposing units/buildings still wins. With no natural
result at the deadline, the match draws. Natural elimination, including mutual elimination,
takes precedence on the final tick. There is no army scoring or lack-of-progress heuristic.

The simulation owns the deadline and latches the result. Neither raw runner stepping nor an
accidental application unpause advances a completed match. Pause freezes time, and restart
retains the rules while clearing tick count, result, and end reason. The HUD shows the clock/limit,
and the result overlay explains a time-limit draw.

Compatibility: the existing RL wrapper explicitly constructs an unbounded-elimination game
internally, retaining its existing independent episode truncation semantics. No ML-facing option,
observation field, reward change, or adapter was introduced.

## Validation

- 15 new tests cover houses only, isolated units, exhausted economy/no base, the real default
  36,000-tick deadline, elimination/combat on the boundary, mutual elimination, base loss with
  remaining structures, pause, restart, result latching, invalid limits, and wrapper compatibility.
- Targeted match/lifecycle/result suite: 24 passed.
- Full suite: **378 passed**, coverage **76.99%**; golden replays unchanged.
- Ruff, formatting, type checks, six-map validation, and core benchmark smoke pass.

Reproduce: `.venv/Scripts/python.exe -m pytest --basetemp=tmp/pytest-c3 --cov=src/rts_nano`.
Remaining work: whole-game acceptance and final documentation in C4.
