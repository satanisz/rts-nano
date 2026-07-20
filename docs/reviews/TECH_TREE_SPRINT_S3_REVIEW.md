# Expanded Tech Tree Sprint S3 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Gameplay and architecture review

Knight, Archer, and Mage are restored as concrete shared content with one neutral definition each.
Knight derives from `MeleeUnit`, Archer from `DeadZoneRangedUnit`, and Mage from `CasterUnit`;
Arclight remains independent artillery. Both faction rosters expose all three shared IDs without
duplicating stats or branching behavior on faction.

Arsenal and Pit train Knight/Archer alongside their advanced faction units. Spire and Chem-Vat
train Mage alongside Arclight/Brute. Registry reverse lookup proves the intended two producers for
every shared unit. Costs and combat values are conservative provisional registry values; numeric
balance remains deferred.

Production-completion tests cover all six producer/unit combinations, runtime class identity, and
the existing rally handoff. Map validation accepts shared units for either faction, while shipped
competitive starting armies remain unchanged. Command-panel labels are generated from the English
display names, and Mage attacks use the existing magic-missile presentation path.

## Asset review

The required six team sprites and three portraits were already tracked before this sprint and load
successfully through the shared cache. Every shared unit was rendered for both team colors by the
asset suite. No duplicate or generated image was added.

`red_mage.png` is intentionally a larger 1024 px transparent source than the other world sprites.
It was visually inspected and is a valid full-body RUST Mage, not a temporary sheet or accidental
portrait. The presentation cache decodes it once and fits it to the unit square; headless mode does
not load it. Source normalization may be done later with UI polish, but is not required for correct
simulation or rendering.

## Determinism and validation

| Check | Result |
|---|---|
| Ruff format | passed; 95 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Focused roster/asset/production/replay tests | 79 passed before rally fixture |
| Full pytest | 261 passed |
| Coverage | 74.86% |
| Golden replay | unchanged: `0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167` |
| Shipped map validation | 6/6 passed |

## Performance

| Scenario | Metric | S3 result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 2.078 ms | below 20 ms |
| Map 01 | Throughput | 9,352.074 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,574.764 ms | below 5,000 |
| Dispersed 400 | Throughput | 122.904 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.027 MiB | comparable |

Existing maps do not spawn the new units, so their benchmark state is intentionally identical. All
budgets pass and headless memory remains unchanged.

## Artifact and safety review

The ignored `.coverage` file was removed after results were recorded. No map, golden replay, PNG,
XCF, cache, preview, or generated runtime file changed. Existing ignored asset-development folders
remain untouched.

## Decision

Sprint S3 makes the shared baseline roster playable for both factions without affecting existing
armies or deterministic behavior. Sprint S4 may add canonical upgrade definitions and team state.
