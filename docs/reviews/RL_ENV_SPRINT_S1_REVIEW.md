# RL Environment Sprint S1 Review

Date: 2026-07-20
Verdict: **APPROVED**

`RtsNanoEnv` now owns a default 36,000-frame limit, episode and decision counters, natural
termination, time-limit truncation, boundary precedence, terminal-step protection, and complete
step metadata. Reset clears lifecycle and built-in delta reward state. Headless stepping reports
actual frames and stops at the paused terminal boundary.

The first benchmark exposed redundant per-frame state/result checks. Review removed them in favor
of the manager's existing pause invariant, restoring throughput before acceptance.

## Validation

- Ruff format/lint and Ty: passed.
- Focused lifecycle/environment/reward/AI/map tests: 57 passed before the reset soak addition.
- Full suite: 299 passed; 75.05% coverage.
- Fifty repeated resets retain stable entity counts and restart public entity IDs.
- ScriptedAI completes all three maps; windowed lifecycle code is unchanged.
- Final full environment benchmark: 1,944.2 decisions/s at skip 1; 923.5 at skip 8.
- Both results remain inside the 15% S0 budget.
- No map, image, AI, balance, tensor, or training code changed.

Sprint S2 may add simultaneous joint decisions on this lifecycle.
