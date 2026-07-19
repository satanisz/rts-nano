# Core Performance Baseline — `cc100d6`

Recorded: 2026-07-19
Executive plan: `EXECUTIVE_PLAN_05_CORE_READINESS.md`, Sprint S0

## Reference machine

- CPU: Intel Core Ultra 9 275HX
- OS: Windows 11 Pro
- Python: 3.14.4
- Pygame CE: 2.5.7
- Power mode and background load were not controlled; values are regression references, not
  cross-machine requirements.

## Reproduction

```powershell
uv run python benchmarks/core_baseline.py --repeats 3 --map-steps 2000 --stress-steps 200
uv run python -m rts_nano.benchmark
```

`core_baseline.py` reports medians. Python allocation peaks are measured separately with
`tracemalloc` so instrumentation does not distort timing samples.

## Baseline results

| Scenario | Metric | Result |
|---|---|---:|
| Map 01 core tick | Cold headless initialization | 2.942 ms |
| Map 01 core tick | Throughput over 2,000 ticks | 8,429 steps/s |
| Map 01 core tick | Peak traced Python allocations | 0.225 MiB |
| 400-unit dispersed stress | Two group attack-move orders | 2,634.027 ms |
| 400-unit dispersed stress | Throughput over 200 ticks | 97.474 steps/s |
| 400-unit dispersed stress | Peak traced Python allocations | 0.984 MiB |
| Existing public environment facade | Throughput over 2,000 steps | 1,812 steps/s median |

The core-tick and public-facade measurements are intentionally separate. The facade builds an
immutable observation after every step, while the core benchmark measures gameplay simulation
only. Sprint S5 profiles these costs independently and establishes CI-safe budgets.

## Historical comparison

Before `cc100d6`, local measurements on the same machine showed approximately:

- 2.627 s cold map initialization,
- 3,260 core ticks/s for the first 500 ticks,
- 13.766 s for 200 stress ticks using global entity scans.

After `cc100d6`, visual-free construction and spatial queries removed those dominant costs.
The S0 numbers above are the formal baseline for all Executive Plan 05 refactors.

## Interpretation rules

1. Compare medians using the same command, machine, and power mode.
2. Treat a repeatable regression above 10% as a review trigger, not an automatic failure.
3. Never trade deterministic correctness for a benchmark improvement.
4. Update this baseline only for an explicitly reviewed architecture or gameplay change.
