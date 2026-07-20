# Worker-Building Sprint 1 Review

Date: 2026-07-20
Status: accepted

## Delivered

- Multiple Peasants can contribute deterministic construction work to one allied building.
- Right-click on an unfinished allied building assigns additional selected Peasants.
- Completed construction releases every assigned builder and advances their deferred orders.
- Right-click on a damaged completed allied building assigns selected Peasants to repair it.
- Repair consumes Wood through deterministic prepaid HP credit with no floating-point economy state.
- Build and repair rates, plus repair efficiency, live in the canonical content definitions.
- Active builder and repairer counts are visible in the English selection panel.
- Build and repair orders support the existing bounded Shift queue.

Construction aggregates work by stable building entity ID before mutating progress. The result does
not depend on renderer activity or incidental collection ordering. Single-Peasant construction
retains its previous timings.

## Verification

- Two Peasants apply exactly two construction frames per simulation tick.
- All builders detach safely when construction completes.
- Multiple Peasants repair a damaged Base and consume the expected Wood.
- The Pygame right-click path assigns both additional builders and repairers.
- Registry validation rejects negative worker rates and invalid repair efficiency.
- Existing construction chaining, cancellation, replay, maps, and presentation boundaries remain
  protected by the full quality gate.

Final gate: 228 tests passed. The benchmark measured 15,228 idle steps/s, 98.6 steps/s with 400
units, 1.027 MiB peak Python memory, and 1,707 ms for two 400-unit group orders. The stress run
remains above the established 60 steps/s and below the 5,000 ms group-order budgets.
