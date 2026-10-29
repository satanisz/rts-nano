# MEMORY

Plan 05 records the completed historical core architecture migration. Plans 06 and 07 describe
later technology-tree and environment work already present in the repository.

For the current game-stage status, read `docs/reviews/GAME_CLOSEOUT_C4_REVIEW.md`,
`docs/GAME_RULES.md`, and `EXECUTIVE_PLAN_08_GAME_STAGE_CLOSEOUT.md`.
The original `docs/reviews/GAME_STAGE_AUDIT_2026-10-28.md` describes the pre-fix baseline.

The user authorized executing C1–C4 as separately committed sprints. C1 fixes weighted population
and dead-worker work; C2 fixes player targeting through fog; C3 freezes elimination plus a
36,000-tick draw deadline. C4 verifies all three v3 maps and four faction pairings, fixes an
additional worker/base path issue found during acceptance, and records UI/performance/memory evidence.
Recent audit/rules/plan text and all new sprint reports are English. `EXECUTIVE_PLAN_01.md` is a
historical Polish document last changed in June 2026, outside the recent translation request.

This closes the bounded game stage, not a competitive-balance certification or ML integration.
The scope excludes preparing an API for ML, new content, and RL training. The existing environment
received only the C3 compatibility wiring needed to preserve its prior episode-limit semantics.
The user subsequently authorized an additional two-bot spectator mode with deliberate planning.
`EXECUTIVE_PLAN_09_BOT_SPECTATOR.md` records its three sprints. The Pygame-free `MatchController`
owns participants/lifecycle; presentation-owned `MatchView` supplies All/Blue/Red visibility and
read-only inspection. Bots keep separate knowledge. The S3 acceptance exposed repeated identical
failed scout searches; one bounded failed-request cache avoids those retries while preserving the
existing strategy and recorded gameplay. See `docs/BOT_SPECTATOR.md` and the S3 review for operation
and evidence. Default Play mode and frozen simulation rules remain available.
Wait for the user's next scope decision; do not infer authorization for the remaining ML backlog.
