# Expanded Tech Tree Sprint S8 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Gameplay and architecture review

RUST now has Frenzy or Pack Knights, Venom or Skirmisher Archers, and Plaguecaller or Mutagenist
Mages. Advanced Mutations and Concentrated Toxins are explicit Chem-Vat follow-ups. Pack derives a
maximum of four contributors from a local spatial query only for Knights carrying that behavior.
Poison refreshes one canonical stack. Toxic Cloud and Mutagenic Surge query one bounded area, sort
targets by entity ID, cap their result, and create no persistent area object.

Temporary mutation state expires centrally and does not alter canonical definitions. All choices
are registry-owned and use the same production, upgrade, ability, effect, and spawn paths as AEGIS.
No global RUST doctrine scan was introduced.

## Validation

| Check | Result |
|---|---|
| Ruff format | passed; 103 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Full pytest | 289 passed |
| Coverage | 74.63% |
| Core golden replay | unchanged |
| Technology replay | passed; `0f5c00aeb392c44da98a41711128cd40a35396b227628dcc3b7469fab1671cda` |
| Shipped map validation | 6/6 passed |

Focused tests cover all three exclusive groups, low-health Frenzy, Pack cap, advanced behavior,
Venom refresh, Skirmisher trade-off, both casts, energy payment, and stable target caps. The replay
now includes AEGIS control, RUST area poison, and cross-faction combat state.

## Performance

| Scenario | Metric | Result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 2.367 ms | below 20 ms |
| Map 01 | Throughput | 7,061.688 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,065.426 ms | below 5,000 |
| Dispersed 400 | Throughput | 179.143 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.028 MiB | comparable to 1.027 MiB |

The standard median benchmark passes every budget. The idle sample was noisier than S7, while the
stress sample improved; neither doctrine performs work for units that have not unlocked it.

## Artifact and safety review

No map, PNG, preview, cache, AI, reward, or RL adapter changed. The technology replay update is the
only intentional snapshot change. Ignored coverage output was removed before commit.

## Decision

Sprint S8 is complete. Both faction trees are mechanically complete and ready for the generated
English tech-tree view, authoring documentation, and final stage audit in Sprint S9.
