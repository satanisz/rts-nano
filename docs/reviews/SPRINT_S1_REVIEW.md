# Sprint S1 Review — Central Content Registry

Date: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`
Verdict: **APPROVED**

## Scope reviewed

- immutable definitions for every current unit, building, resource, and faction,
- one validated and read-only `ContentRegistry`,
- definition-backed entity behavior without local numeric stat tables,
- registry-backed production, construction, command-panel, state, and environment queries,
- compatibility of the public package facade and the temporary `game/data.py` facade,
- table-driven runtime parity tests for all 17 content definitions,
- deterministic replay, rendering, map validation, and performance smoke checks.

## Correctness findings

No gameplay rule, serialized map, cost, timing, combat value, or faction roster changed. The S0
golden replay still produces this digest in consecutive fresh simulations:

```text
239c2b1b85c30a2d07526157f622dc297f844b04ed5ce2b63b692e02138f5c90
```

Concrete classes now select a behavior and inject one registry definition. Movement, life,
combat, shield, poison, frenzy, splash, construction, resource, and vision values are copied
from that definition at entity creation. Production and construction retain only temporary
class/legacy-roster routing; they no longer contain private design values.

## Registry review

Startup validation rejects:

- duplicate IDs within a category or across content categories,
- missing or inconsistent producers,
- missing building and unit requirements,
- missing produced units,
- building tech-tree cycles,
- foreign or duplicate faction roster entries,
- faction-owned content omitted from every roster,
- negative costs/combat values and non-positive geometry, durations, life, or movement values.

Definition dataclasses are frozen and slotted. Registry indexes use read-only mapping proxies.
The compatibility mappings in `game/data.py` reference those same indexes and cannot diverge.

## Architecture findings

Importing `rts_nano.content` in a fresh process does not import Pygame. The public package facade
was made lazy so lightweight domain modules no longer trigger environment, manager, SDL, or
presentation imports. Accessing `RtsNanoEnv` through the existing public API still loads and
returns the same environment class.

The S0 direct-Pygame debt allowlist did not grow. Entity presentation remains tracked S3 debt;
legacy rosters, duplicated behavior factories, and color-to-faction mapping remain tracked S2
work.

## Quality gate

| Check | Result |
|---|---|
| Ruff check | Passed |
| Ruff format check | Passed, 65 files formatted |
| Ty | Passed |
| Pytest | 152 passed |
| Coverage | 66.67% (50% requirement passed) |
| Map 01 validation | Passed |
| Map 02 validation | Passed |
| Map 03 validation | Passed |
| Deterministic replay | Passed twice in one test; digest unchanged |
| Registry headless import | Passed; Pygame absent from `sys.modules` |
| Public facade import | Passed |
| Render smoke | Passed with 254 entities |
| Headless benchmark smoke | Passed |
| `git diff --check` | Passed |

## Performance review

The one-sample post-S1 smoke run reported:

- map 01 cold init: 3.243 ms,
- map 01 core throughput: 8,414 steps/s over 500 ticks,
- 400-unit group orders: 2,680 ms,
- 400-unit throughput: 97.096 steps/s over 50 ticks.

These results remain consistent with the formal S0 medians (2.942 ms, 8,429 steps/s, 2,634 ms,
and 97.474 steps/s respectively). Registry lookup is concentrated at creation and command
boundaries and caused no significant simulation regression.

## Safety review

- Existing user artwork, source images, and temporary files remain unstaged and unmodified by
  the sprint commit.
- Compatibility mappings preserve current imports while all canonical values live in one place.
- No map schema, observation schema, balance value, RL module, or AI behavior changed.
- The migration remains reversible as one sprint-scoped commit.

## Decision

Sprint S1 meets its exit criteria and is approved for commit. Sprint S2 may begin after the S1
commit is created successfully.
