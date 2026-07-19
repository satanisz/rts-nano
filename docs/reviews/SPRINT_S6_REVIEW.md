# Sprint S6 Review — Documentation, CI, and Stage Closure

Date: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`
Implementation commit: `95005b4`
Verdict: **APPROVED**

## Documentation review

The README now describes the AEGIS and RUST rosters, current gameplay, installation, launch,
validation, headless benchmarking, and the local quality gate. It explicitly scopes AI, balance,
reward, environment lifecycle, and RL work to the next stage.

`ARCHITECTURE.md` matches the implemented content → simulation/game systems → application →
presentation dependency direction. It documents the shared windowed/headless simulation, tick
order, `EntityStore`, dynamic obstacles, and ownership rules. `MAP_SCHEMA.md` explains schema
version 2, serialized team IDs, explicit faction IDs, faction-independent colors, entity payloads,
grouped terrain, ramps, rocks, resources, and validation.

The new content guide makes one immutable definition the normal extension point and permits a new
factory behavior only for a genuinely new mechanic. The determinism guide records stable entity
ordering, system order, spatial/path tie-breaking, safe spawn ordering, replay rebaseline policy,
and sources of nondeterminism to avoid. No current document describes Knight/Archer/Mage as the
roster or links to an ambiguous generic plan filename.

## CI review

Two GitHub Actions workflows run on pushes and pull requests:

- quality: Ruff format, Ruff check, and Ty;
- tests: pytest with coverage/replay gate, all shipped map validators, dummy-SDL rendering, and a
  report-only benchmark smoke sample.

Both workflows use Python 3.14, the locked development dependencies, read-only repository
permissions, and the official uv action with dependency caching. Test output and benchmark results
are not cached. Performance thresholds remain report-only until CI runner variance is observed.

## Clean-checkout verification

A detached worktree at implementation commit `95005b4` was created without local assets or caches.
From that checkout, `uv sync --locked --dev` completed without manual setup, followed by:

| Check | Result |
|---|---|
| Ruff format / Ruff check | Passed |
| Ty | Passed |
| Pytest | 181 passed |
| Coverage | 71.48% in detached-path measurement; 50% requirement passed |
| Replay digest | Passed |
| All three shipped maps | Passed |
| Dummy-SDL render suite | Passed separately, 20 tests |
| Benchmark smoke | 14,092 map steps/s; 187 dispersed stress steps/s |

The temporary worktree was removed after verification.

## Stage decision

Executive Plan 05 meets its definition of done. The game has one registry, one generic runtime
store, a Pygame-independent simulation, deterministic replay and spawn/repath behavior, measured
scaling, current English documentation, and automated quality gates. No AI, balance, or RL scope was
introduced. A separate Executive Plan 06 may now define those systems against the stable game core.
