# Expanded Tech Tree Sprint S4 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Architecture review

The content layer now owns immutable `UpgradeDefinition` and `StatModifier` records plus closed
upgrade, exclusivity-group, and modifier-stat identifiers. Registry construction validates faction
ownership, research buildings, affected content, costs, durations, unique modifiers, prerequisites,
cycles, symmetric conflicts, and exclusivity groups. The production registry remains empty until
the doctrine sprints, so S4 changes no live game values.

`TeamState` stores completed IDs once in canonical order. `UpgradeSystem` validates a completion,
inserts its ID, and recomputes only affected living entities in stable `entity_id` order. Effective
stats always begin at immutable unit/building definitions and apply completed upgrades in sorted ID
order. A production spawn receives the same derivation once, after entering the runtime store.

Maximum-life and maximum-shield transitions preserve existing damage/depletion by adding the
capacity delta and clamping decreases. Attack cooldown is untouched. Re-completion is rejected, and
completion order cannot compound modifiers. Upgrade logic is invoked only on completion or spawn;
the simulation runner has no idle upgrade traversal.

## Validation

| Check | Result |
|---|---|
| Ruff format | passed; 97 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Focused upgrade/registry/spawn/replay tests | 47 passed |
| Full pytest | 265 passed |
| Coverage | 75.12% |
| Golden replay | unchanged: `0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167` |
| Shipped map validation | 6/6 passed |

## Performance

| Scenario | Metric | S4 result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 2.501 ms | below 20 ms |
| Map 01 | Throughput | 8,021.935 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,727.627 ms | below 5,000 |
| Dispersed 400 | Throughput | 98.015 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.027 MiB | comparable |

All budgets pass. Identical traced memory and the absence of an upgrade call in the idle runner
confirm that the new system has no steady-state cost before research is used.

## Artifact and safety review

The gate-created `.coverage` file was removed. No asset, map, preview, golden replay, cache, or
generated file changed. AI, rewards, environment adapters, and RL code are untouched.

## Decision

Sprint S4 provides a deterministic upgrade core with no gameplay delta when teams have no completed
research. Sprint S5 may connect it to the building activity queue and English command UI.
