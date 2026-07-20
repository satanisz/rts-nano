# Expanded Tech Tree Sprint S5 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Activity queue review

Every production building now owns one typed FIFO of unit and research activities. Only its first
item advances. Unit jobs retain their compatibility accessors, population reservation, safe spawn,
refund, observations, and `(producer, unit)` rally handoff. Existing AI and RL actions continue to
see unit production only; no research action or reward change was added to those layers.

Research validation covers faction, researching building, active building state, completed and
reserved duplicates, prerequisites, required buildings, exclusive completed/reserved siblings, and
resources before payment. Reservation and payment happen atomically. Player cancellation releases
the reservation and refunds 75%; researcher destruction releases every reservation and refunds
nothing. Completion is team-local and delegates stat application to `UpgradeSystem`.

The English command panel derives research buttons, costs, locks, queue progress, and cancellation
from registry data. Building selection details show active and completed research. The public
headless-safe `can_research` and `research_upgrade` methods contain no Pygame dependency.

## Validation

| Check | Result |
|---|---|
| Ruff format | passed; 98 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Focused activity/UI/production/env/replay tests | 93 passed |
| Full pytest | 269 passed |
| Coverage | 74.61% |
| Golden replay | unchanged: `0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167` |
| Shipped map validation | 6/6 passed |

Focused research fixtures prove mixed unit/research sequencing, partial refunds, destruction loss,
independent simultaneous teams, clean restart state, and reservation release.

## Performance

| Scenario | Metric | S5 result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 1.289 ms | below 20 ms |
| Map 01 | Throughput | 16,229.551 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,054.460 ms | below 5,000 |
| Dispersed 400 | Throughput | 184.471 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.027 MiB | comparable |

The activity system returns immediately when every queue is empty. All budgets pass with identical
traced memory.

## Artifact and safety review

The ignored `.coverage` file was removed after recording results. No asset, map, preview, replay,
cache, generated file, AI implementation, reward, or RL adapter changed.

## Decision

Sprint S5 delivers a complete deterministic research lifecycle while preserving production and
rallies. Sprint S6 may add the reusable caster energy and ability command path.
