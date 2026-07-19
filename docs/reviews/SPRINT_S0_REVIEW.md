# Sprint S0 Review — Baseline and Architectural Contracts

Date: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`
Verdict: **APPROVED**

## Scope reviewed

- repeatable core and 400-unit performance baseline,
- versioned deterministic replay and readable golden checkpoints,
- explicit direct-Pygame dependency boundary,
- inventory of current definitions, factories, and legacy rosters,
- stable domain vocabulary for content, entity, team, faction, category, and combat role,
- plan and memory pointer alignment.

## Correctness findings

No gameplay rule or balance value changed.

The golden replay covers:

- movement,
- gather/deposit economy,
- worker construction and population cap,
- unit production,
- direct combat,
- AEGIS shields,
- RUST poison,
- Arclight splash,
- elimination victory.

Two fresh simulations produce the same SHA-256 digest:

```text
239c2b1b85c30a2d07526157f622dc297f844b04ed5ce2b63b692e02138f5c90
```

The stored JSON checkpoint is intentionally compact enough for a useful pytest diff when a
future refactor changes behavior.

## Architecture findings

Direct Pygame imports in non-UI game modules are locked to the existing debt set:

- `assets/entities/base_entities.py`,
- `manager.py`,
- `terrain.py`.

The allowlist cannot grow. S3 must remove the entity dependency and S4 must remove manager and
terrain dependencies.

The migration inventory confirms three duplicate creation paths and legacy class-based rosters.
No attempt was made to solve them in S0; they are assigned to S1 and S2 as planned.

## Quality gate

| Check | Result |
|---|---|
| Ruff check | Passed |
| Ruff format check | Passed, 61 files formatted |
| Ty | Passed |
| Pytest | 127 passed |
| Coverage | 66.73% |
| Map 01 validation | Passed |
| Map 02 validation | Passed |
| Map 03 validation | Passed |
| Deterministic replay | Passed twice in one test |
| Render smoke | Passed with 254 entities |
| Headless benchmark smoke | Passed |
| `git diff --check` | Passed |

## Performance review

Formal medians are stored in `benchmarks/BASELINE_CC100D6.md`. A post-change smoke run reported:

- map 01 cold init: 3.096 ms,
- map 01 core throughput: 8,513 steps/s over 500 ticks,
- 400-unit group orders: 2,590 ms,
- 400-unit throughput: 98.912 steps/s over 50 ticks.

These results are consistent with the formal S0 baseline and show no regression from `cc100d6`.

## Known constraints accepted for later sprints

1. `tracemalloc` reports Python allocations, not total process RSS. This is sufficient for the
   S0 approximate memory baseline; S5 adds deeper memory profiling if needed.
2. The import-boundary test tracks direct imports. S4 adds a fresh-process transitive import
   assertion after the pure simulation package exists.
3. Existing environment-facade throughput is recorded separately from core tick throughput
   because it builds an immutable observation on every step.

## Safety review

- Existing user artwork and working files were not modified by S0.
- No generated benchmark output was written outside explicitly tracked documentation.
- No schema, map, public gameplay API, or balance value changed.

## Decision

Sprint S0 meets every exit criterion and is approved for commit. Sprint S1 may begin after the
S0 commit is created successfully.
