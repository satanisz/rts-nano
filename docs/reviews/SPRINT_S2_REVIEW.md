# Sprint S2 Review — Generic Entity, Team, and Faction Model

Date: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`
Verdict: **APPROVED**

## Scope reviewed

- one stable, generic `EntityStore` for all runtime entities,
- indexes by entity ID, team, category, and content ID with creation-order iteration,
- one validated `EntityFactory` shared by map loading, production, and construction,
- generic system, observation, selection, UI, victory, and environment queries,
- explicit team faction assignment independent of display color,
- schema-versioned migration of all shipped maps,
- complete removal of historical class rosters and color-to-faction fallbacks.

## Correctness findings

`EntityStore` assigns monotonic IDs starting at one and retains an entity's identity after its
removal. Every secondary index is updated together with the primary index. Query results are
stable because they follow primary creation order rather than set or hash order.

Teams now own explicit `team_id` and `faction_id` values. Tests prove that Blue can use RUST,
Red can use AEGIS, and two teams can use the same faction. Map validation rejects content that
does not belong to the team's declared faction. All three shipped maps use schema version 2 and
declare factions explicitly.

The S0 golden replay remains unchanged:

```text
239c2b1b85c30a2d07526157f622dc297f844b04ed5ce2b63b692e02138f5c90
```

## Architecture findings

There is no runtime roster named after a historical unit or building. Production,
construction, and map loading no longer choose destination lists. `EntityFactory` contains the
only mapping from a content ID to the concrete behavior class and validates exact coverage of
the content registry at import time.

The former `EntitiesGroup`, `ResourcesGroup`, `FACTION_BY_TEAM`, legacy roster attributes, and
temporary definition facade have been removed. Entity visuals and direct Pygame imports remain
tracked S3 debt; this sprint did not expand that boundary.

## Quality gate

| Check | Result |
|---|---|
| Ruff check | Passed |
| Ruff format check | Passed, 68 files unchanged |
| Ty | Passed |
| Pytest | 156 passed |
| Coverage | 66.84% (50% requirement passed) |
| Map 01 validation | Passed |
| Map 02 validation | Passed |
| Map 03 validation | Passed |
| Deterministic replay | Passed; digest unchanged |
| Faction independence tests | Passed |
| Render smoke | Passed with 254 entities |
| Headless benchmark smoke | Passed |
| `git diff --check` | Passed |

## Performance review

The post-S2 smoke run reported:

- map 01 cold initialization: 3.041 ms,
- map 01 core throughput: 8,789 steps/s over 500 ticks,
- 400-unit group orders: 2,490 ms,
- 400-unit throughput: 96.261 steps/s over 50 ticks,
- peak traced Python memory: 0.248 MiB for map 01 and 1.013 MiB for the stress case.

This is consistent with the S0 medians (2.942 ms, 8,429 steps/s, 2,634 ms, and 97.474 steps/s).
The indexed world model did not introduce a meaningful performance or allocation regression.

## Safety review

- Existing user artwork, source images, and temporary files remain unstaged and unmodified by
  the sprint commit.
- Gameplay values, AI behavior, RL code, reward behavior, and observation shape did not change.
- Stable iteration and the unchanged replay protect combat-resolution ordering.
- The three map migrations are explicit, validator-covered, and reversible with this sprint.

## Decision

Sprint S2 meets all exit criteria and is approved for commit. Sprint S3 may begin after the S2
commit is created successfully.
