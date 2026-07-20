# Expanded Tech Tree Sprint S6 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Caster model review

The content registry now validates immutable ability definitions with closed target/effect kinds,
integer energy cost, cooldown, range, duration, radius, target cap, and magnitude. Upgrades grant
ability IDs explicitly. Mage's canonical definition has 100 energy and deterministic 1/6 energy per
frame regeneration; only `CasterUnit` owns energy, regeneration accumulator, and sparse active
cooldowns. Arclight remains plain `ArtilleryUnit` with none of that state.

`cast` is a first-class order with a stable ability ID, optional stable target entity ID, and/or
immutable ground destination. It can be Shift-queued. Normal commands replace it without payment.
Targeted casts follow the living target into range; final ownership/life/range/energy/cooldown checks
occur immediately before effect application. Energy and cooldown are committed only after an effect
succeeds. Lost targets skip cleanly, and insufficient energy waits while local integer regeneration
continues.

The command panel exposes unlocked English ability names with energy/cooldown feedback, targeting
mode, and Shift queueing. Selection details show current/max energy. The pure ability system has no
Pygame import and does not alter rewards, AI, or RL actions.

## Performance finding and correction

The first implementation called `update_cast` for every unit and relied on its immediate type/order
guard. Although budgets passed, review rejected that avoidable virtual call. The runner now invokes
AbilitySystem only when a unit already has an active `cast` order. Energy and cooldown work remains
local to actual CasterUnit updates, with sparse cooldown dictionaries.

After that change idle throughput improved from 8,046.185 to 11,490.383 steps/s and stress
throughput from 99.390 to 118.484 steps/s in consecutive samples. No all-caster or all-ability scan
exists.

## Validation

| Check | Result |
|---|---|
| Ruff format | passed; 100 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Focused cast/research/UI/replay tests | 32 passed |
| Full pytest after optimization | 274 passed |
| Coverage | 74.09% |
| Golden replay | unchanged: `0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167` |
| Shipped map validation | 6/6 passed |

Focused tests cover confirmed payment, cooldown, Shift queue, interruption, target death,
insufficient energy, integer regeneration, artillery separation, and invalid definitions.

## Final performance

| Scenario | Metric | S6 result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 1.666 ms | below 20 ms |
| Map 01 | Throughput | 11,490.383 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 2,016.924 ms | below 5,000 |
| Dispersed 400 | Throughput | 118.484 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.028 MiB | comparable to 1.027 MiB |

## Artifact and safety review

The ignored `.coverage` file was removed. No PNG, map, preview, replay snapshot, cache, AI, reward,
or RL adapter changed.

## Decision

Sprint S6 provides the reusable deterministic caster path with bounded idle cost. Sprint S7 may add
AEGIS doctrine definitions and effects without new command infrastructure.
