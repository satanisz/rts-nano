# RTS Nano — Executive Plan 07: RL Environment Foundation

Last updated: 2026-07-20

## STATUS: IN PROGRESS — S2 COMPLETED

This plan prepares the deterministic headless environment for later tensor, vector-environment,
and PyTorch work without changing game rules, ScriptedAI, balance, maps, or the playable single
player path. It starts after commit `28ad0ed`, with 292 passing tests.

Execution order:

`S0 Contracts → S1 Episode Lifecycle → S2 Joint Actions → S3 Strategic Actions → S4 Tactical Actions and Closure`

Every sprint ends with focused tests, a single-player regression, the complete quality gate, an
appropriate benchmark, a review document, artifact cleanup, and one commit.

## Executive decisions

- `RtsNanoEnv` defaults to a 36,000-frame episode limit; `None` disables it.
- A natural result on the boundary wins over time-limit truncation.
- `step_joint()` validates both teams against one pre-step state and advances time once.
- Each team may submit at most 16 commands; joint commands must carry `frames == 1`.
- Invalid policy commands become reported no-ops while independent legal commands execute.
- Shared resource, queue, research, and placement claims use a deterministic validation ledger.
- Cross-team placement collisions reject both placements as `joint_conflict`.
- New joint results return rewards for Blue and Red separately.
- Legacy `step(Action)` and scalar rewards remain compatible throughout this plan.
- The windowed `ScriptedAI.step() → GameSession.update()` loop remains unchanged and protected.

## Sprint outcomes

### S0 — Contracts and compatibility

Publish the public types, denial semantics, migration boundary, and single-player invariant without
changing runtime behavior.

### S1 — Deterministic episode lifecycle

Add termination/truncation, frame limit, episode/decision counters, terminal-step protection,
repeatable reset, and lifecycle soak coverage.

### S2 — Simultaneous joint actions

Add normalize/validate/resolve/apply/advance/observe phases, action outcomes, team rewards, command
caps, deterministic resource claims, and the compatibility wrapper.

### S3 — Strategic action parity

Make production registry-driven and expose research, activity cancellation, all rally modes,
repair, construction assistance, and queued strategic orders. Add the minimum observation fields
needed to choose those actions legally.

### S4 — Tactical actions and closure

Expose entity/ground Mage casts and queue parity, add action-facing energy/cooldown/ability state,
protect the complete contract with a readable joint replay, document it, and close the plan with
actual measurements.

## Definition of Done

- every playable unit, building, research choice, rally mode, repair/build-assist path, and Mage
  ability is reachable through typed headless actions;
- Blue and Red act on the same decision state and receive separate rewards;
- every episode terminates or truncates and requires reset afterward;
- replay results do not depend on mapping order;
- legacy environment callers continue to work;
- windowed single player and ScriptedAI complete all competitive maps;
- headless does not import Pygame or load assets;
- tests, maps, replays, type checks, lint, and performance budgets pass.

Tensor schemas, parametric tensor masks, ScenarioSpec, curriculum/evaluation maps, multiprocessing,
Gymnasium, PyTorch/PPO, reward design, AI strategy, and balance remain deferred to Plan 08.
