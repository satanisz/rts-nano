# Plan 08 — Game Stage Closeout

Date: 2026-10-28. Status: **approved for sprint execution; implementation in progress**.
Basis: [audit](docs/reviews/GAME_STAGE_AUDIT_2026-10-28.md) and
[verified rules](docs/GAME_RULES.md).

Goal: close the small deterministic RTS game as a stable subject for later RL experiments.
This plan excludes preparing an ML API or independently expanding the existing `env.py` layer.

## Definition of completion

The stage closes when existing rules are consistent, known bugs G1–G3 are resolved, match endings
are explicit and verified, and acceptance covers both factions and all three target maps.
No additional content is required. Historical green tests are necessary but do not replace
regression tests for newly discovered bugs.

## C1 — Economy and tick integrity

Status: **complete** — [C1 review](docs/reviews/GAME_CLOSEOUT_C1_REVIEW.md).

Fix G1 (population) and G3 (dead builders).

- Separate unit count from the sum of unit population costs. Production and HUD must use the
  appropriate quantity. Reservations must remain consistent across multiple producers,
  cancellation, spawning, and death.
- Set the supply-loss policy: keep the existing army and block new production requests when
  supply is insufficient; explicitly define what happens to previously paid queue entries.
  This is a gameplay decision, not an API schema.
- Construction and repair must ignore workers with HP <= 0, including workers killed earlier
  in the same tick before world cleanup.

Acceptance: mixed armies costing 1/2/3 population, a full cap, multiple queues, destruction of a
house or producer, and worker death in combat. No free work, negative resources, or accidental
release of population when training finishes.

## C2 — Target selection and fog of war

Status: **complete** — [C2 review](docs/reviews/GAME_CLOSEOUT_C2_REVIEW.md).

Fix G2 with a shared object-selection rule for selection, right-click, gather commands, rally,
and casts. Hostile targets must be visible when selected; resources must satisfy the chosen
exploration rule. Clicking empty or hidden ground may issue a coordinate order, but must not
reveal an object or store its ID.

Document visibility loss after a legal target selection: whether tracking continues or the unit
moves to the last known position. Existing tracking must not change accidentally while fixing
click handling. Terrain occlusion by rocks or elevation is not required.

Acceptance: left/right clicks, command panel, rally, and casts for visible, explored-but-hidden,
and never-explored targets; rediscovery and restart. Tests must exercise actual player input,
not only `OrderSystem`.

## C3 — Freeze match-ending rules

Status: **complete** — [C3 review](docs/reviews/GAME_CLOSEOUT_C3_REVIEW.md).
Accepted rule: elimination plus a 36,000-tick draw deadline, with elimination taking precedence.

Retain or explicitly change elimination of all objects. The minimal recommendation is to retain
elimination, add a simulation-time match limit, and draw at that limit without army scoring.
A natural result on the final tick takes precedence. Start acceptance with 36,000 ticks
(10 nominal gameplay minutes); this was a proposal in the audit, not an existing windowed-game rule.

Any alternative requires an equally explicit description, such as losing all bases ending the
match. Do not introduce automatic lack-of-progress detection without defining progress. The
existing RL wrapper limit cannot be presented as a fix for the game.

Acceptance: a single winner, mutual elimination, houses only, a unit isolated by terrain, depleted
resources, no base, a result exactly at the limit, pause, and restart. Every scenario must have
an expected outcome or a known upper bound on its duration.

## C4 — Whole-game acceptance and version freeze

After C1–C3, run the three-map/four-faction-pairing matrix:
AEGIS/RUST, RUST/AEGIS, AEGIS/AEGIS, and RUST/RUST. Reverse roles and command order in scenarios
comparing sides. Do not infer balance from simple-bot wins.

Minimum evidence:

1. Start → gather both resources → house → basic and advanced producer → research → ability →
   combat → result → restart, for both factions.
2. Worker/base loss, resource depletion, blocked production exit, cancellation, unreachable route,
   and supply loss during production; predictable behavior without hangs or unbounded memory/queues.
3. Two fresh executions of the same commands produce the same state; key replays also pass in
   separate processes with different `PYTHONHASHSEED` values.
4. Full quality gate, six maps, render smoke, and key UI paths. Visual acceptance covers fog,
   construction, queues, F9, result, and restart, with recorded observations rather than launch only.
5. Tick and command timing for active v3 gameplay and a long active economy/combat run. Keep the
   v2/400-unit benchmark as a reference. Record the machine, repetitions, and budget; do not treat
   cross-machine timing differences as direct evidence of regressions.

Closeout requires no open G1–G3 bugs, accepted C3 rules, a C4 report, current rules, and an identified
game-version commit. When mechanics change, update affected golden replays with an explanation;
never rebaseline solely to make a test pass.

## Frozen scope

Do not add maps, factions, units, doctrines, a new bot, expansions, campaigns, or an editor for this
acceptance. Basic playability and fair rules are required; competitive 50/50 balance is not.
Excluded: ML API design, new observations/masks, tensors, reward shaping, Gymnasium/PettingZoo,
training, curricula, and multi-environment infrastructure.

Execution order: **C1 → C2 → C3 → C4**, with a separate commit per sprint. This is a bounded
closeout of existing mechanics, not another content expansion.
