# Build Chain Sprint 3 Review

Date: 2026-07-20
Status: accepted

## Delivered

- Construction represented as a first-class active `build` order on the assigned Peasant.
- Shift-right-click on wood or gold appends gathering behind active construction.
- The queued gather starts in the same deterministic tick in which construction completes.
- Canceling an unfinished building releases a surviving worker to its next queued order.
- A normal non-Shift command still interrupts current work and clears deferred orders.
- English selection-panel labels for active work and up to three queued orders.
- Player controls and the simulation tick/handoff architecture documented in English.

The construction state machine remains authoritative for progress and cancellation. The order
system only records player intent and advances the already bounded queue, keeping construction,
gathering, and Pygame presentation independent.

## Verification

- Direct simulation API builds a House before starting a queued wood harvest.
- The actual Pygame Shift-right-click path produces the same build-to-gather chain.
- Canceling construction advances to a queued live resource safely.
- UI formatting resolves canonical content definitions to English display names.
- Existing order, rally, gathering, construction, map, rendering-boundary, and deterministic replay
  tests remain green.
- Ruff formatting/lint, Ty type checking, full Pytest suite, and the core benchmark pass.

Final gate: 225 tests passed. The benchmark measured 15,270 idle steps/s, 176.0 steps/s with 400
units, 1.027 MiB peak Python memory in the 400-unit case, and 1,143 ms for two 400-unit group
orders. These remain within the established game-core budgets.

## Review decision

Accepted. The three command-flow sprints now form one coherent system: bounded deterministic unit
queues, Base rally orders for produced Peasants, and construction-to-economy chaining visible in
the UI. AI policies, automated balance work, and RL changes remain deliberately out of scope.
