# RL Environment Sprint S4 Review

Date: 2026-07-20
Verdict: **APPROVED — PLAN 07 COMPLETE**

The public environment now exposes the complete game action surface needed before tensorization.
`CastAction` supports entity and ground targets through the existing `AbilitySystem`. Observation
schema v4 reports Mage energy, cooldowns, target modes, and unlocked abilities. Tactical and worker
commands use one bounded Shift-order queue, including attack-move, patrol, target attack,
return-cargo, construction assistance, repair, and casts.

A readable joint golden replay protects simultaneous Blue/Red casts, canonical outcomes, tactical
effects, cooldowns, follow-up movement, and mapping-order normalization. README, architecture, and
the RL contract now describe the implemented boundary and explicitly defer tensor/Gymnasium/
PyTorch work.

## Review findings

- Non-queued order paths retain their former implementations; queue support is additive.
- Cast validation and execution delegate to the same unlock, target, energy, cooldown, range, and
  effect rules used by the game UI.
- Snapshot IDs, not Pygame selection, identify casters and targets.
- Caster snapshot work is conditional and performs one type check per entity; maps without Mages
  do not scan abilities.
- ScriptedAI, balance, map content, assets, rendering behavior, and reward design were unchanged.
- No tensor framework or training dependency was introduced.

## Validation

- Ruff format/lint and Ty: passed.
- Focused tactical/joint/replay tests: 18 passed.
- Full suite: 318 passed.
- Branch coverage: 75.32% (50% project gate).
- Readable joint replay: repeatable and golden-matched.
- All three MapSpec v3 files: valid; ScriptedAI completes all three in the full suite.
- Presentation-boundary regression: passed under the test suite.
- Core smoke: 10,376 idle frames/s and 93.5 stress-400 frames/s. The idle sample varied with host
  load; stress throughput and traced memory stayed stable at 1.028 MiB.
- Warm environment smoke: 1,652 legacy skip-1 decisions/s and 942 joint skip-8 decisions/s.
- Diff whitespace and temporary-artifact review: passed. Existing ignored virtual environments
  were not modified or committed.

The next plan may define tensor observations/actions, parametric masks, training/evaluation
scenarios, vector environments, rewards, Gymnasium/PyTorch adapters, and policy training.
