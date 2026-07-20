# Expanded Tech Tree S0 Baseline

Date: 2026-07-20
Commit under test: `8129391`
Command: `uv run python benchmarks/core_baseline.py`

## Quality baseline

| Check | Result |
|---|---|
| Ruff format | 93 files formatted |
| Ruff lint | passed |
| Ty | passed |
| Pytest | 235 passed in 60.81 s |
| Coverage | 74.72% (50% gate passed) |
| Golden replay | passed as part of pytest |
| Headless/presentation boundary | passed as part of pytest |
| Shipped map validation | 6/6 passed |

## Performance baseline

Three-sample medians from the standard benchmark:

| Scenario | Metric | S0 result | Plan budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 1.132 ms | below 20 ms |
| Map 01 | Core throughput | 16,476.202 steps/s | at least 6,000 steps/s |
| Map 01 | Peak traced Python memory | 0.217 MiB | comparable to baseline |
| Dispersed 400 | Two group orders | 1,112.303 ms | below 5,000 ms |
| Dispersed 400 | Core throughput | 174.304 steps/s | at least 60 steps/s |
| Dispersed 400 | Peak traced Python memory | 1.027 MiB | comparable to 1.027 MiB |

All performance budgets pass. Later sprint measurements must run without another test or benchmark
process competing for CPU time.
