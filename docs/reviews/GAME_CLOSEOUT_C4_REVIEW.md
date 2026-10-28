# Game Closeout C4 — Acceptance and Version Freeze

Date: 2026-10-28. Status: complete.

**The bounded game stage is closed.** The current game is a deterministic subject for later RL
experiments, with explicit rules, bounded ordinary matches, and repeatable acceptance of the
existing map/faction set. This is not an ML API readiness claim or competitive-balance certification.

The frozen revision is the commit containing this review, `benchmarks/game_closeout.py`, its CI
job, and the attached acceptance data. It follows documentation/translation `b0d0731`, C1 `220346e`,
C2 `ddbfde7`, and C3 `369fe05`. See [Plan 08](../../EXECUTIVE_PLAN_08_GAME_STAGE_CLOSEOUT.md) and
[Game Rules](../GAME_RULES.md). The [original audit](GAME_STAGE_AUDIT_2026-10-28.md) remains a
historical report of revision `8e06cd5`; its unresolved verdict does not describe this revision.

## Acceptance matrix

The committed driver uses the original map starts, three workers per side, zero starting bank,
and normal gameplay commands. Both sides earn wood/gold, build a House plus both producer tiers,
train a Knight and Mage, research their Mage doctrine, move to the central arena, cast Arc Bind
or Toxic Cloud, fight, reach the match deadline, and restart. No funds, units, research completion,
damage, or tick jumps are injected into these runs.

The controller assigns resource jobs, retries idle work orders, selects legal reachable building
positions, sets producer rallies, and stages the fight. It is an acceptance script, not an upgrade
to `ScriptedAI`. It deliberately uses `MatchRules(max_frames=18000)`; the ordinary game remains
36,000 ticks. Every one of the 48 runs reaches a time-limit Draw after combat; no faction-strength
or natural-elimination frequency conclusion follows from that staged outcome.

| Map | AEGIS / RUST | RUST / AEGIS | AEGIS / AEGIS | RUST / RUST |
|---|---|---|---|---|
| Crown Divide | PASS | PASS | PASS | PASS |
| Twin Rivers | PASS | PASS | PASS | PASS |
| Ashen Circuit | PASS | PASS | PASS | PASS |

Each cell covers Blue→Red and Red→Blue command submission, with two fresh worlds per order:
**12 pairings × 2 orders × 2 repetitions = 48 runs / 864,000 simulated ticks**.
All 24 paired final-state digest comparisons pass. Reversed command order is a distinct scenario,
not a claim that differently ordered commands produce identical states. Latest progression/combat
milestone: tick 11,311. Each run records 3,781–4,577 ticks with at least one worker actively
gathering, depositing, or constructing; travel and idle frames are excluded from that counter.
Restart checks clear time, result, bank, and completed research while preserving match rules.

Raw machine information, milestones, results, digests, and timings:
[matrix.json](assets/game-closeout-c4/matrix.json).

## Defects discovered during C4

- **Worker exit/path consistency:** on Ashen Circuit a Red gold worker could remain idle beside
  its Base after the normal build chain. Grid search checked the first edge from the cell center,
  and overlap escape accepted an edge based only on its farther endpoint. Local movement correctly
  rejected the actual first step toward the Base center, preventing continued deposits/research.
  Pathfinding now checks exact start/goal connections, including same-cell goals; overlap escape
  must move outward from its first step. A minimal regression completes a real gather/deposit
  cycle beside the original Base/Pit/Chem Vat layout. Endpoint/overlap regressions also cover the
  geometric failure directly.
- **Queue feedback:** a producer now shows training progress as well as research progress, its
  next job, and waiting count. The FIFO semantics and costs are unchanged.
- **Terminal UI:** the result replaces open F9/menu overlays and no longer has a duplicate
  pause/result caption underneath. Image-comparison regressions protect both cases.

The existing core, technology, and joint golden replays are unchanged. This means their protected
scenarios are unaffected; other historical paths may legitimately change with the corrected routing.

## Edge-case evidence

| Requirement | Automated evidence |
|---|---|
| Weighted population, reservations, supply/producer loss | `test_population_and_worker_integrity.py`, `test_research_queue.py` |
| Dead worker cannot construct/repair, including combat death | `test_population_and_worker_integrity.py` |
| Base loss, no base/resources, houses only, isolation, terminal boundary | `test_match_rules.py` |
| Finite resource replacement and depleted rally | `test_headless.py`, plus the finite-resource macro driver |
| Blocked spawn retains paid job and resumes when clear | `test_core_hardening.py::test_completed_production_waits_until_a_safe_spawn_point_exists` |
| Cancellation/refund/reservation release | `test_headless.py`, `test_research_queue.py`, C1 regressions |
| Unreachable order stops without a retry loop | `test_core_hardening.py::test_unreachable_order_stops_without_repath_loop` |
| Fog-aware mouse/keyboard/card selection, gather, rally, cast | 30 cases in `test_player_visibility.py` |
| Actual building-exit route and deposits | `test_worker_base_exit.py`, `test_pathfinding.py`, all map-3 macro cases |
| Default 36,000-tick result and restart | `test_match_rules.py`, active soak below |

## Performance and memory

Machine: Windows 11 build 26200, Intel64 Family 6 Model 198 Stepping 2, Python 3.14.4, local `.venv`.
No coverage or tracing during matrix timing. Samples are local review evidence, not cross-machine
guarantees. Review budgets: sustained active-v3 throughput >=60 ticks/s, mean command batch <=16.67 ms,
observed command batch maximum <=100 ms, and active retained Python growth <2 MiB. These are review
budgets; host-dependent timing is not a strict CI threshold. CI enforces progression and repeatability.

| Active v3 workload | Median ticks/s (16 runs) | Slowest run ticks/s | Median wall time / 18,000 ticks |
|---|---:|---:|---:|
| Crown Divide | 4,859.90 | 3,488.64 | 3.840 s |
| Twin Rivers | 5,635.69 | 5,515.39 | 3.251 s |
| Ashen Circuit | 5,556.43 | 5,432.80 | 3.322 s |

Step throughput excludes command dispatch and driver bookkeeping; wall time includes both.
Worst per-run mean command batch: 0.263 ms; largest individual command batch: 39.854 ms.
Largest observed simulation step: 42.173 ms. Average throughput passes the budget; these numbers
do not promise every windowed frame meets a 16.67 ms deadline.

The [active soak](assets/game-closeout-c4/soak.json) advances the ordinary **36,000-tick** deadline
on Crown Divide, including earned economy, construction, research, abilities, and combat.
It includes 5,490 worker-work ticks, 1,200 bounded command batches, and a verified result/restart.
After GC, retained traced Python allocation grows **0.0214 MiB** from the tick-1,000 warm-up to the
end, passing the 2 MiB budget. This mixed economy/combat/idle scenario is not continuous mass combat;
it is stronger evidence than an idle-only memory probe, not proof of no possible leak. Native SDL
allocations are not measured. Its 39.897 s wall time includes `tracemalloc` overhead and must not
be compared directly with untraced performance.

Legacy v2/400-unit reference: [core-benchmark.json](assets/game-closeout-c4/core-benchmark.json).
Three repetitions, 200 ticks per scenario, untraced medians:

| Reference workload | Ticks/s | Historical S5 review budget |
|---|---:|---:|
| Idle legacy map 01 | 6,925.424 | >=6,000 |
| Active legacy economy | 3,570.428 | >=2,500 |
| 80-unit combat | 577.811 | >=350 |
| 400 dispersed units | 141.240 | >=60 |
| 400 close-combat units | 33.226 | >=25 |

All reference budgets pass. Idle initialization is 2.726 ms (<20 ms); 400-unit group orders take
1,904.222 ms (<5,000 ms). Idle retained allocation after 5,000 ticks rounds to 0.000 MiB.
The 400-unit combat figure is a stress result and does not imply 60 FPS at that army size.

## Visual acceptance

Six real Pygame renderer frames at **1280×720** were inspected. They are committed PNGs, generated
by `benchmarks/game_closeout_visuals.py` using dummy SDL. This is a rendered-state inspection with
synthetic input, not a human desktop playtest. The visual fixture supplies funding and jumps to the
last tick to prepare views; those shortcuts are absent from the macro and soak evidence.

| View | Recorded observation |
|---|---|
| [Fog/start](assets/game-closeout-c4/01-fog-start.png) | Starting base/workers and explored area visible; unknown terrain black; HUD clock and population fit. |
| [Construction](assets/game-closeout-c4/02-construction.png) | Unfinished House, progress, builder count, and cancel command visible. |
| [Queue](assets/game-closeout-c4/03-queue.png) | Mage training percentage, following Arcbinder job, waiting count, and reserved population visible. |
| [F9](assets/game-closeout-c4/04-f9.png) | Technology names, costs, requirements, and current research state readable; long descriptions deliberately ellipsized. |
| [Result](assets/game-closeout-c4/05-result.png) | Deadline Draw replaces still-open F9; reason and both buttons visible without overlapping captions. |
| [Restart](assets/game-closeout-c4/06-restart.png) | Real R input posts the restart event; reset view matches start, with zero bank/time and fresh fog. |

Both factions' mechanical progression is covered by the matrix; these six visual fixtures use
the Blue AEGIS perspective. Existing render-smoke tests also exercise the current content adapters.
Cosmetic improvements such as HUD contrast and richer text layout remain optional, outside closeout.

## Final quality gate and reproduction

| Check | Result |
|---|---|
| Full pytest with statement/branch coverage | **385 passed**, 57.34 s; **76.91%** coverage (required 50%) |
| Ruff check / format / ty | PASS; 120 Python files formatted; benchmark helpers also type-checked |
| Shipped maps | **6/6 PASS**, v2 and v3 |
| Core + technology + joint replay tests, process with hash seed 1 | **6/6 PASS** |
| Same replay tests, separate process with hash seed 97 | **6/6 PASS** |
| Full progression matrix | **48/48 PASS**, 24 repeated final-state comparisons |
| Active memory soak / reference benchmark | PASS against the review budgets above |
| Rendering/parity and result/input regression tests | PASS in full pytest; six frames also visually inspected |

Seven regression cases were added in C4; the total increased from 378 to 385. Remote GitHub CI was
configured but not executed by this local review. A first local map-validation invocation passed
a literal wildcard through PowerShell; expanding the six paths explicitly produced the successful
validation above. That invocation error was not a map failure.

From the repository root, using the locked environment (or the equivalent `.venv` executable):

```text
python -m pytest --basetemp=tmp/pytest-c4 --cov=src/rts_nano
ruff check .
ruff format --check .
ty check src/rts_nano
python benchmarks/game_closeout.py --repeats 2 --output tmp/c4-matrix.json
python benchmarks/game_closeout.py --soak --output tmp/c4-soak.json
python benchmarks/core_baseline.py --extended --repeats 3 --scenario-steps 200
python benchmarks/game_closeout_visuals.py
```

For display-free visual regeneration, set `SDL_VIDEODRIVER=dummy` and `SDL_AUDIODRIVER=dummy`.
Validate maps with explicit filenames; in PowerShell, expand paths before invoking Python:

```powershell
$closeoutMaps = @(Get-ChildItem -LiteralPath src/rts_nano/maps -Filter '*.json' | ForEach-Object FullName)
.venv/Scripts/python.exe -m rts_nano.validate_map @closeoutMaps
```

For cross-process replay checks, run the three replay test files separately with `PYTHONHASHSEED=1`
and `PYTHONHASHSEED=97`, using distinct workspace `--basetemp` directories.

## Scope boundary

No new content, maps, strategy bot, ML adapter, observation schema, reward, or training code is
introduced. The existing environment only received the C3 compatibility wiring that preserves its
previous independent episode limit. Recent Polish audit/rules/plan text was translated to English;
all closeout reports are English. The June 2026 historical Plan 01 was not part of that recent text.

There is no known open G1–G3 or C4-discovered blocker in this frozen scope. Further ML work, bot
development, balance studies, and presentation polish require the user's next scope decision.
