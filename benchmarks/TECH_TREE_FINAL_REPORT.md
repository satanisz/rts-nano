# Expanded Tech Tree Final Performance Report

Date: 2026-07-20

## Standard headless gate

Command: `uv run python benchmarks/core_baseline.py`

| Scenario | Metric | Result | Budget |
|---|---:|---:|---:|
| Map 01 | Cold initialization | 2.061 ms | below 20 ms |
| Map 01 | Throughput | 7,882.401 steps/s | at least 6,000 |
| Map 01 | Peak memory | 0.217 MiB | comparable |
| Dispersed 400 | Two group orders | 1,457.651 ms | below 5,000 |
| Dispersed 400 | Throughput | 125.109 steps/s | at least 60 |
| Dispersed 400 | Peak memory | 1.028 MiB | comparable to 1.027 MiB |

## Completed-tree scenario

Command: `uv run python benchmarks/technology_scenario.py`

The scenario completes one legal doctrine path for each faction, applies AEGIS Arc Bind and RUST
Toxic Cloud, measures their 120-frame active window, then advances 5,000 additional upgraded match
ticks. It contains 42 combat units and two production bases.

| Window | Result |
|---|---:|
| Both Mage effects active | 947.392 steps/s |
| Further 5,000 upgraded ticks | 1,974.598 steps/s |

The result confirms that completed upgrades and temporary effects remain bounded and that the F9
view adds no headless dependency or tick work.
