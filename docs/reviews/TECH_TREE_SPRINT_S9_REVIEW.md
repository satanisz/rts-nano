# Expanded Tech Tree Sprint S9 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED — PLAN COMPLETE**

## Player experience and architecture review

F9 opens an English technology view for the currently controlled faction. Rows are generated from
`ContentRegistry` and expose research building, cost, prerequisites, exclusive-choice consequence,
affected units or granted ability, description, and live available/researching/completed/excluded
state. The command panel continues to expose exact active research progress, Mage energy, and
cooldowns where actions are executed. Input is blocked behind the overlay and F9 closes it.

The UI owns only a boolean visibility flag and immutable display rows. Rendering parity proves that
opening and drawing the view cannot advance or mutate gameplay. Headless modules do not import the
view or Pygame. The executable graph validator checks producer legality, grants, and two-member
doctrine groups; registry construction continues to reject cycles, missing dependencies, invalid
content, and malformed definitions.

## Documentation and authoring review

README now lists shared units, doctrine research, and the F9 control. Architecture, content, and
determinism guides explain ownership and replay rules. The new authoring guide defines the canonical
upgrade, exclusivity, ability, bounded targeting, temporary-effect, test, and benchmark workflow.

## Final validation

| Check | Result |
|---|---|
| Ruff format | passed; 106 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Full pytest | 292 passed |
| Coverage | 74.87% |
| Core replay | unchanged: `0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167` |
| Technology replay | passed: `0f5c00aeb392c44da98a41711128cd40a35396b227628dcc3b7469fab1671cda` |
| Shipped maps | 6/6 passed |

The standard benchmark passed every budget: 2.061 ms cold start, 7,882.401 idle steps/s, 125.109
stress steps/s, and 0.217/1.028 MiB peak traced memory. The completed-tree benchmark measured
947.392 steps/s with both Mage effects active and 1,974.598 steps/s for the following 5,000 ticks.

## Artifact and scope audit

No PNG, map, preview, cache, generated screenshot, AI policy, automated balance, reward, observation,
environment lifecycle, or RL adapter changed in S9. The ignored coverage file was removed. New
files are source, tests, English documentation, or a repeatable benchmark only.

## Decision

Executive Plan 06 is complete. Knight, Archer, and Mage are shared baseline units with mechanically
distinct AEGIS and RUST doctrine trees, deterministic research and abilities, bounded performance,
and a playable registry-derived UI. AI, balance evaluation, and RL work remain deferred to the next
plan as requested.
