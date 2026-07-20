# Expanded Tech Tree Sprint S0 Review

Date: 2026-07-20
Executive plan: `EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md`
Verdict: **APPROVED**

## Scope and migration inventory

Sprint S0 changes documentation only. Runtime behavior, content values, maps, assets, AI, rewards,
and RL code are unchanged.

Legacy behavior inheritance is confined to `simulation/entities/units.py`: Guardian, Ripper, and
Brute inherit Knight; Marksman and Spitter inherit Archer; Arclight inherits Mage. The three names
are re-exported only by `simulation/entities/__init__.py`. No factory, map, observation, or UI stores
one of those behavior-class names as a content ID.

The reciprocal producer contract is confined to `UnitDefinition.produced_at`, seven unit entries in
the registry, registry validation, `ProductionSystem.can_enqueue_unit`, and focused registry/data
tests. Runtime production enumeration already reads `BuildingDefinition.produces`; S2 can therefore
make that tuple authoritative without changing commands, observations, or RL-facing action shapes.

The exact research, modifier, exclusivity, refund, queue, cast, temporary-effect, and determinism
rules are fixed in `docs/TECH_TREE_CONTRACTS.md`. Required future fixtures are listed there.

## Validation

| Check | Result |
|---|---|
| Ruff format | passed; 93 files already formatted |
| Ruff lint | passed |
| Ty | passed |
| Pytest | 235 passed |
| Coverage | 74.72% |
| Existing golden replay | passed within pytest |
| All legacy and MapSpec maps | 6/6 valid |
| Standard benchmark | all plan budgets passed |

Performance results are recorded in `benchmarks/TECH_TREE_S0_BASELINE.md`.

## Artifact and safety review

`git status --short` was clean before Sprint S0. No generated image, map preview, coverage report,
cache, or temporary file is part of this change. Existing ignored local asset sources and preview
workspaces were left untouched because they predate this sprint and may contain intentional work.

## Decision

The migration surface is bounded, implementation semantics are explicit, and the baseline is
healthy. Sprint S1 may proceed with a behavior-only hierarchy refactor and must preserve the replay
digest and benchmark budgets.
