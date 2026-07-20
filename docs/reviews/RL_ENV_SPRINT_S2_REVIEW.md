# RL Environment Sprint S2 Review

Date: 2026-07-20
Verdict: **APPROVED**

`step_joint()` now normalizes Blue and Red in canonical order, prevalidates both batches, reserves
resources, resolves placement conflicts, applies accepted actions, and advances the simulation once.
Invalid policy commands are reported no-ops. The 16-command cap and fixed joint frame contract are
enforced. Per-team reward functions return a complete Blue/Red reward map and reset with episodes.

The legacy scalar `step(Action)` path remains intact. ScriptedAI and the Pygame loop do not import
or call the joint executor.

## Validation

- Ruff format/lint and Ty: passed.
- Focused joint tests: 7 passed.
- Full suite: 306 passed; 75.04% coverage.
- Tests cover mapping-order invariance, both-team application, independent invalid no-op, resource
  overspend, symmetric placement conflict, batch/frame limits, and per-team rewards.
- ScriptedAI completes all three competitive maps as part of the full suite.
- Joint skip-8 throughput: 961.0 decisions/s.
- Legacy skip-1 throughput: 2,023 decisions/s.
- No game rule, map, AI, image, balance, tensor, or training dependency changed.

Sprint S3 may extend the typed action surface through this stable executor.
