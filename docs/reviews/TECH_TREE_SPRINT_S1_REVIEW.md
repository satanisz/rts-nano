# Expanded Tech Tree Sprint S1 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Implementation review

The historical Knight, Archer, and Mage behavior parents were replaced with `MeleeUnit`,
`DeadZoneRangedUnit`, `CasterUnit`, and `ArtilleryUnit`. Guardian/Ripper/Brute share melee behavior,
Marksman/Spitter share dead-zone ranged behavior, and Arclight now inherits artillery directly.
Caster and artillery are independent subclasses of Unit, so future Mage energy and ability state
cannot leak into Arclight.

The retired content-named bases are no longer defined or exported. Concrete factory mappings,
content IDs, definitions, attacks, shields, poison, frenzy, dead zones, and splash code are
unchanged. Focused hierarchy and combat tests prove the new relationships.

## Review finding resolved

Randomized full-suite execution exposed an existing test leak: another viewport test may resize the
module-level presentation dimensions, while five command-panel tests built their reference layout
from constants captured at import time. The production click could then miss its button even though
the UI implementation correctly used the manager's current viewport. Those tests now use
`manager.screen_width` and `manager.screen_height`, matching runtime behavior. The isolated test and
two subsequent full-suite runs established the cause; no gameplay code changed for this finding.

## Determinism and validation

| Check | Result |
|---|---|
| Ruff format | passed; 94 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Focused hierarchy/combat/replay tests | 24 passed |
| Full pytest | 238 passed |
| Coverage | 74.72% |
| Golden replay | unchanged: `0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167` |
| Shipped map validation | 6/6 passed |

## Performance

| Scenario | Metric | S0 | S1 | Budget |
|---|---:|---:|---:|---:|
| Map 01 | Throughput | 16,476.202 | 13,551.044 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,112.303 | 1,235.850 ms | below 5,000 |
| Dispersed 400 | Throughput | 174.304 | 168.547 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.027 | 1.027 MiB | comparable |

The hierarchy adds no per-frame work or entity state. Observed throughput variance is comfortably
inside every budget, and traced memory is identical.

## Artifact and safety review

The coverage run created only the ignored `.coverage` measurement file; it was removed after the
result was recorded. No PNG, asset source, map preview, cache, golden snapshot, or generated runtime
file changed. Existing ignored workspaces remain untouched.

## Decision

Sprint S1 preserves gameplay and determinism, removes misleading inheritance, and passes all
quality and performance gates. Sprint S2 may make the building producer graph authoritative.
