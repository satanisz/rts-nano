# Expanded Tech Tree Sprint S7 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Gameplay and architecture review

AEGIS now has two exclusive doctrines for every shared tier-two unit: Bulwark or Vanguard for
Knight, Longshot or Arcshot for Archer, and Shieldweaver or Arcbinder for Mage. Shield Network and
Arc Targeting provide explicit advanced follow-ups. Barrier Pulse uses stable, capped targeting;
Arc Bind applies deterministic slow and arc-mark state. Hold, charge, range, mark, shield, and
ability behavior is activated through registry-owned upgrades rather than faction conditionals.

Temporary combat state is sparse. Units without the relevant behavior do not receive per-instance
charge state, and effect cleanup restores derived speed without accumulating modifiers. Spatial
queries are local to casts and combat interactions; no global doctrine scan was introduced.

## Validation

| Check | Result |
|---|---|
| Ruff format | passed; 102 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Full pytest | 283 passed |
| Coverage | 74.55% |
| Core golden replay | unchanged |
| Technology golden replay | passed; `801e41327249961655d4793aee11f794d17b787362eb3f645ef979ca5d3547fb` |
| Shipped map validation | 6/6 passed |

Tests cover exclusivity, charge, hold, long range, arc marking, shield selection, binding effects,
effect expiry, and deterministic technology replay.

## Performance

| Scenario | Metric | Result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 1.517 ms | below 20 ms |
| Map 01 | Throughput | 11,948.702 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,993.454 ms | below 5,000 |
| Dispersed 400 | Throughput | 153.877 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.028 MiB | comparable to 1.027 MiB |

## Artifact and safety review

No map, PNG, preview, cache, AI, reward, or RL adapter changed. Coverage output is ignored and was
removed before commit. The only new snapshot is the intentional readable technology replay golden.

## Decision

Sprint S7 is complete. The same registry, upgrade, ability, temporary-effect, and deterministic
replay paths are suitable for the RUST doctrines in Sprint S8.
