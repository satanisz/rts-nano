# Sprint S5 Review — Correctness, Scaling, and Performance Hardening

Date: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`
Verdict: **APPROVED**

## Correctness review

Runtime mutations now update the spatial index in the same tick. Movement updates entities
incrementally when they cross cells; spawn, construction, cancellation, and death add or remove
their entries immediately. High-speed movement uses a swept local query, and splash candidates are
queried around the impacted target, including across cell boundaries.

Completed production chooses the nearest valid point on a deterministic producer-centered lattice.
The point must be inside world bounds, clear of water and rocks, and clear of living units and
buildings. Search is bounded to 128 world units. If no point is valid, the paid job remains complete
at the front of the queue and retries on later ticks; it is neither lost nor refunded implicitly.

Building additions and removals increment an obstacle revision. Active routes are recalculated once
when that revision changes. A route that cannot be found now leaves the unit idle with
`path_unreachable=True`; attack-move is cleared and patrol is cancelled instead of retrying forever.
Neutral resources intentionally remain nonblocking, as documented in entity collision and terrain
tests.

Boundary coverage includes high-speed cell changes, splash across cells, tower acquisition in edge
cells, clamped attack-move destinations, dynamic obstacle add/remove, cancellation, death, and the
existing crowded-unit map/terrain collision case.

## Determinism review

The replay remains repeatable but was intentionally rebaselined for the approved spawn correction.
The produced Marksman now uses the deterministic nearest safe exit at `[150.0, 45.0]` instead of
the legacy fixed point `[150.0, 160.0]`. No combat, economy, timing, or balance checkpoint changed.

New replay digest:

```text
0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167
```

## Performance review

The standard S0 benchmark improved on the reference machine:

- cold map initialization: 1.224 ms,
- map 01: 13,985 steps/s,
- two 400-unit group orders: 1,561 ms,
- dispersed 400-unit simulation: 103.810 steps/s,
- traced peaks: 0.236 MiB for map 01 and 1.005 MiB for stress.

The extended benchmark covers idle, economy, medium combat, dispersed 400, close-combat 400, and
long-run memory retention. Full measurements and initial CI-safe budgets are in
`benchmarks/SPRINT_S5_REPORT.md`.

## Safety review

- No AI policy, balance value, reward, environment lifecycle, or RL adapter was changed.
- No gameplay asset or map content was changed.
- The replay change is isolated and explained by safe spawning.
- User artwork and temporary development files remain unstaged.
- No path cache or flow field was introduced without profiling evidence.

## Decision

Sprint S5 meets its correctness and performance exit criteria. Sprint S6 may begin after the full
quality gate passes and the reviewed changes are committed.
