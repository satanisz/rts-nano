# Game Closeout C1 — Economy and Tick Integrity

Date: 2026-10-28. Status: complete.

G1 is fixed: live population sums definition costs independently of unit count. Production reserves
the same weighted amount across all producers, and spawning transfers it to the live army. The HUD
shows live population/capacity and queued population separately. Dead units awaiting cleanup no
longer count as living units or occupy supply.

Supply-loss policy: existing units remain and paid jobs finish even above the reduced cap. New
requests require sufficient supply. Cancellation releases reservations with the existing 75%
refund; producer destruction releases reservations without a refund.

G3 is fixed: dead workers are excluded from construction/repair work and active-worker counts,
including workers killed during unit combat earlier in the same tick.

The corrected cap exposed an existing bot assumption: two Guardians plus three workers use nine
of ten supply, so a bot waiting for three soldiers never attacks. The existing launch condition now
allows a smaller nonempty army when supply prevents training any roster unit and no units remain
queued. This is compatibility with valid population accounting, not a new bot strategy or roster.

## Validation

- Eight new regression cases cover mixed costs, full-cap rejection without payment, reservations
  across producers, spawn/cancel/death, paid jobs after supply loss, supply-blocked bot launch,
  and both construction and repair with already-dead or combat-killed workers.
- Full suite: **333 passed**, coverage **74.91%**. Existing golden replays remain unchanged.
- Ruff, formatting, type checks, all six maps, and the core benchmark smoke pass.
- The first full run encountered sandbox restrictions on the system temporary directory and the
  bot assumption above. The successful run uses `--basetemp=tmp/pytest-c1` and the corrected bot.

Reproduce: `.venv/Scripts/python.exe -m pytest --basetemp=tmp/pytest-c1 --cov=src/rts_nano`.
Rules are updated in [GAME_RULES](../GAME_RULES.md). G2 and match-ending work remain for C2/C3.
