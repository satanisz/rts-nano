# RL Environment Sprint S3 Review

Date: 2026-07-20
Verdict: **APPROVED**

The headless API now reaches the game's existing strategic systems without duplicating their game
rules. Unit and building IDs are runtime-validated through the central content registry. New typed
actions cover research, unified activity cancellation, ground/resource/enemy rally, repair, and
multi-worker construction assistance. Explicit IDs make these actions independent of selection.

Observation schema v3 adds faction ID, completed/reserved upgrades, and typed unit/research
activity queues. The old production-only queue remains as a compatibility view. Joint research
claims reserve resources and exclusive choices before mutation, so commands in one batch cannot
overspend or queue mutually exclusive doctrines.

## Review findings

- `CancelProductionAction` and `production_queue` remain as compatibility surfaces; the clearer
  `CancelActivityAction` and `activity_queue` are canonical for new integrations.
- Rally delegates to the same producer rally system used by single player. Resources produce a
  gather rally for Bases, enemy entities produce attack-move, and ground points produce move.
- Repair and construction assistance delegate to existing worker order methods and preserve their
  Shift-queue semantics.
- ScriptedAI and the Pygame session were not changed and do not import the RL executor.
- No map, balance value, AI behavior, asset, rendering path, or training dependency changed.

## Validation

- Ruff lint/format and Ty: passed.
- Focused strategic tests: 5 passed.
- Full suite: 311 passed.
- All three shipped MapSpec v3 files: valid.
- ScriptedAI completes all three competitive maps as part of the full suite.
- Core smoke: 14,846 idle simulation frames/s and 93.5 stress-400 frames/s.
- Environment smoke after warm-up: 1,988 legacy skip-1 decisions/s and 1,030 joint skip-8
  decisions/s.
- Diff whitespace check: passed; no generated artifacts found.

Sprint S4 may add tactical cast parity and the final replay/documentation gate.
