# Expanded Tech Tree Sprint S2 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Implementation review

`UnitDefinition.produced_at` has been removed. `BuildingDefinition.produces` is now the only
writable production graph, and `ContentRegistry.producers_for_unit` derives its reverse index once
at startup in canonical building-ID order. `ProductionSystem.can_enqueue_unit` checks only the
selected building definition, so shared units can be trained by more than one faction producer
without duplicated unit definitions or hardcoded IDs.

Registry startup now rejects duplicate production links, unknown unit links, units with no
producer, and faction-specific units linked from a shared or foreign-faction building. Shared units
remain legal in shared or faction-specific producers. The content authoring guide documents the
single source of truth and reverse lookup.

Focused tests cover one producer, two producers for a shared unit, wrong-faction production,
missing producers, duplicate links, unsupported reverse lookup, runtime production, UI production,
rallies, and the unchanged replay. No current costs, timings, rosters, or building production tuples
changed.

## Determinism and validation

| Check | Result |
|---|---|
| Ruff format | passed; 94 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Focused registry/production/replay tests | 96 passed |
| Full pytest | 243 passed |
| Coverage | 74.81% |
| Golden replay | unchanged: `0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167` |
| Shipped map validation | 6/6 passed |

## Performance

| Scenario | Metric | S2 result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 2.382 ms | below 20 ms |
| Map 01 | Throughput | 8,079.881 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,761.384 ms | below 5,000 |
| Dispersed 400 | Throughput | 144.010 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.027 MiB | comparable |

All budgets pass. This sprint adds only one registry-startup derivation and removes a comparison
from production requests; it adds no per-frame work. Lower idle throughput than the immediately
preceding sample is therefore treated as host variance, with memory and stress throughput stable.

## Artifact and safety review

The ignored `.coverage` file created by the gate was removed after recording results. No asset,
PNG, source image, map preview, replay snapshot, or generated runtime file changed. Repository-wide
search confirms `produced_at` remains only in historical planning/review prose, not executable code
or current authoring instructions.

## Decision

Sprint S2 establishes one deterministic, many-to-many production graph and preserves current game
behavior. Sprint S3 may restore Knight, Archer, and Mage as shared concrete content.
