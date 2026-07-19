# Order Queue Sprint 1 Review

Date: 2026-07-20
Status: accepted

## Delivered

- Deterministic per-unit queues for move and gather orders.
- Normal commands replace active intent and clear queued work.
- Shift commands append behind active work and execute in insertion order.
- A hard limit of 16 deferred orders per unit.
- Stable entity IDs for deferred resource targets.
- Shared public order paths for headless callers and Pygame right-click input.
- Invalid or depleted deferred resource targets are skipped safely.

The low-level movement and gathering state machines remain unchanged. `OrderSystem` tracks only units
with non-empty queues, avoiding an all-unit scan each tick. Empty queues use lists rather than deques
to avoid significant per-unit memory overhead in large idle simulations.

## Verification

- Sequential move orders reach both destinations in order.
- Move followed by gather begins harvesting only after movement completes.
- A non-Shift move clears the pending queue.
- Shift-right-click on a resource creates a gather order.
- Queue capacity rejects work beyond 16 entries.
- Golden deterministic replay is unchanged.
- Ruff and Ty pass.

Core benchmark after the memory review:

| Metric | Result | Budget |
|---|---:|---:|
| Idle throughput | 15,091 steps/s | at least 6,000 steps/s |
| 400-unit throughput | 173.3 steps/s | at least 60 steps/s |
| 400-unit peak Python memory | 1.027 MiB | comparable to 1.005 MiB reference |
| Two 400-unit group orders | 1,157 ms | below 5,000 ms |

## Deferred to the next sprints

- Building rally points and production-spawn handoff.
- Construction as a first-class queued order.
- Queue display in the selection UI.
