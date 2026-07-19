# Base Rally Sprint 2 Review

Date: 2026-07-20
Status: accepted

## Delivered

- Per-base ground and resource rally state in the deterministic simulation.
- Right-click ground with a selected base sets a move rally.
- Right-click wood or gold with a selected base sets a gather rally.
- Newly produced Peasants receive the rally through `OrderSystem` immediately after spawning.
- A depleted or removed resource target falls back to the nearest live node of the same kind.
- Selected bases display a persistent rally line and marker; gather rallies use a gold marker.
- Multiple selected bases can receive the same rally through the public headless-safe API.

Production now reports only units spawned in the current tick. It returns a shared empty tuple while
idle, avoiding a per-tick list allocation in the common no-production path. The simulation runner
hands spawned units to the order system; production itself does not know about movement or Pygame.

## Verification

- A produced Peasant reaches a ground rally destination.
- A produced Peasant automatically starts harvesting from a resource rally.
- Depletion before spawn selects a valid same-resource fallback.
- Pygame right-click changes a selected base from move rally to gather rally.
- Presentation boundary tests confirm rendering does not mutate simulation state.
- Existing production, gathering, maps, deterministic replay, and order queue tests remain green.

## Deferred to Sprint 3

- Construction as an active high-level order.
- Shift-queued gathering after construction completion.
- Selection-panel display of active and queued orders.
