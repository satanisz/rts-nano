"""Repeatable core-simulation baseline used by Executive Plan 05.

Run from the repository root:

    uv run python benchmarks/core_baseline.py

The benchmark reports medians rather than a single sample. It intentionally
does not enforce machine-independent thresholds; CI policy is introduced in
Sprint S6 after runner variance has been measured.
"""

from __future__ import annotations

import argparse
import gc
import json
import statistics
import time
import tracemalloc
from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings

MAP_01 = Path("src/rts_nano/maps/map_settings_01.json")


def _stress_settings(unit_count: int = 400) -> MapSettings:
    """Build a large open-map scenario with evenly split, dispersed armies."""
    per_team = unit_count // 2
    blue = [[100 + (index % 20) * 70, 100 + (index // 20) * 70] for index in range(per_team)]
    red = [[3100 - (index % 20) * 70, 2000 - (index // 20) * 70] for index in range(per_team)]
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [],
            "base": [[80, 80]],
            "guardian": blue,
            "marksman": [],
            "arclight": [],
        },
        "Red": {
            "faction_id": "RUST",
            "peasant": [],
            "base": [[3120, 2120]],
            "ripper": red,
            "spitter": [],
            "brute": [],
        },
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 3200,
            "height": 2200,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def _close_combat_settings(unit_count: int = 400) -> MapSettings:
    """Build two dense armies positioned inside immediate acquisition range."""
    settings = _stress_settings(0)
    per_team = unit_count // 2
    settings["Blue"]["guardian"] = [[1250 + (index % 20) * 18, 850 + (index // 20) * 18] for index in range(per_team)]
    settings["Red"]["ripper"] = [[1650 + (index % 20) * 18, 850 + (index // 20) * 18] for index in range(per_team)]
    return settings


def _two_army_settings(unit_count: int = 80) -> MapSettings:
    """Build a medium battle used for active-combat throughput."""
    settings = _stress_settings(0)
    per_team = unit_count // 2
    settings["Blue"]["guardian"] = [[1100 + (index % 10) * 35, 900 + (index // 10) * 35] for index in range(per_team)]
    settings["Red"]["ripper"] = [[1750 + (index % 10) * 35, 900 + (index // 10) * 35] for index in range(per_team)]
    return settings


def _map_sample(steps: int) -> dict[str, float]:
    gc.collect()
    start = time.perf_counter()
    simulation = HeadlessSimulation.from_map_file(MAP_01)
    initialized = time.perf_counter()
    simulation.step(steps)
    finished = time.perf_counter()
    simulation.close()
    elapsed = finished - initialized
    return {
        "cold_init_ms": (initialized - start) * 1000,
        "steps_per_second": steps / elapsed if elapsed > 0 else 0.0,
    }


def _stress_sample(steps: int) -> dict[str, float]:
    gc.collect()
    simulation = HeadlessSimulation.from_settings(_stress_settings())
    manager = simulation.manager
    command_start = time.perf_counter()
    manager.issue_attack_move_order(TeamColor.BLUE, (3000, 2000))
    manager.issue_attack_move_order(TeamColor.RED, (200, 200))
    command_end = time.perf_counter()
    step_start = time.perf_counter()
    simulation.step(steps)
    step_end = time.perf_counter()
    simulation.close()
    elapsed = step_end - step_start
    return {
        "group_orders_ms": (command_end - command_start) * 1000,
        "steps_per_second": steps / elapsed if elapsed > 0 else 0.0,
    }


def _battle_sample(settings: MapSettings, steps: int) -> dict[str, float]:
    """Measure initialization, opposing group orders, and active ticks."""
    gc.collect()
    started = time.perf_counter()
    simulation = HeadlessSimulation.from_settings(settings)
    initialized = time.perf_counter()
    simulation.manager.issue_attack_move_order(TeamColor.BLUE, (2300, 1100))
    simulation.manager.issue_attack_move_order(TeamColor.RED, (900, 1100))
    ordered = time.perf_counter()
    simulation.step(steps)
    finished = time.perf_counter()
    simulation.close()
    elapsed = finished - ordered
    return {
        "cold_init_ms": (initialized - started) * 1000,
        "group_orders_ms": (ordered - initialized) * 1000,
        "steps_per_second": steps / elapsed if elapsed > 0 else 0.0,
    }


def _economy_sample(steps: int) -> dict[str, float]:
    """Measure workers actively gathering and returning resources."""
    gc.collect()
    started = time.perf_counter()
    simulation = HeadlessSimulation.from_map_file(MAP_01)
    initialized = time.perf_counter()
    manager = simulation.manager
    for team in (TeamColor.BLUE, TeamColor.RED):
        workers = manager.state.entities_by_content_id("peasant", team=team)
        resources = manager.state.resources_by_content("wood")
        if workers and resources:
            manager.issue_gather_order(team, resources[0], workers)
    ordered = time.perf_counter()
    simulation.step(steps)
    finished = time.perf_counter()
    simulation.close()
    elapsed = finished - ordered
    return {
        "cold_init_ms": (initialized - started) * 1000,
        "orders_ms": (ordered - initialized) * 1000,
        "steps_per_second": steps / elapsed if elapsed > 0 else 0.0,
    }


def _idle_retained_memory(steps: int = 5000) -> float:
    """Return traced Python memory growth across a long idle simulation."""
    gc.collect()
    simulation = HeadlessSimulation.from_map_file(MAP_01)
    tracemalloc.start()
    gc.collect()
    before, _ = tracemalloc.get_traced_memory()
    simulation.step(steps)
    gc.collect()
    after, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    simulation.close()
    return round((after - before) / (1024 * 1024), 3)


def _peak_python_memory(*, stress: bool) -> float:
    """Measure approximate Python allocation peak without distorting timing samples."""
    gc.collect()
    tracemalloc.start()
    simulation = (
        HeadlessSimulation.from_settings(_stress_settings()) if stress else HeadlessSimulation.from_map_file(MAP_01)
    )
    simulation.step(1)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    simulation.close()
    return round(peak_bytes / (1024 * 1024), 3)


def measure_baseline(*, repeats: int = 3, map_steps: int = 2000, stress_steps: int = 200) -> dict[str, object]:
    """Measure map and stress scenarios and return median metrics."""
    sample_count = max(1, repeats)
    map_samples = [_map_sample(map_steps) for _ in range(sample_count)]
    stress_samples = [_stress_sample(stress_steps) for _ in range(sample_count)]

    def medians(samples: list[dict[str, float]]) -> dict[str, float]:
        return {key: round(statistics.median(sample[key] for sample in samples), 3) for key in samples[0]}

    return {
        "map_01": {
            "steps": map_steps,
            **medians(map_samples),
            "peak_python_mib": _peak_python_memory(stress=False),
        },
        "stress_400": {
            "steps": stress_steps,
            **medians(stress_samples),
            "peak_python_mib": _peak_python_memory(stress=True),
        },
        "repeats": sample_count,
    }


def measure_extended(*, repeats: int = 3, steps: int = 200) -> dict[str, object]:
    """Measure every Sprint S5 workload using scenario medians."""
    sample_count = max(1, repeats)

    def median_samples(samples: list[dict[str, float]]) -> dict[str, float]:
        return {key: round(statistics.median(sample[key] for sample in samples), 3) for key in samples[0]}

    return {
        "idle_map_01": median_samples([_map_sample(steps) for _ in range(sample_count)]),
        "active_economy": median_samples([_economy_sample(steps) for _ in range(sample_count)]),
        "two_army_combat": median_samples([_battle_sample(_two_army_settings(), steps) for _ in range(sample_count)]),
        "dispersed_400": median_samples([_stress_sample(steps) for _ in range(sample_count)]),
        "close_combat_400": median_samples(
            [_battle_sample(_close_combat_settings(), steps) for _ in range(sample_count)]
        ),
        "idle_retained_mib_5000_steps": _idle_retained_memory(),
        "repeats": sample_count,
        "steps_per_scenario": steps,
    }


def main() -> None:
    """Run the baseline and print machine-readable JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--map-steps", type=int, default=2000)
    parser.add_argument("--stress-steps", type=int, default=200)
    parser.add_argument("--extended", action="store_true")
    parser.add_argument("--scenario-steps", type=int, default=200)
    args = parser.parse_args()
    results = (
        measure_extended(repeats=args.repeats, steps=args.scenario_steps)
        if args.extended
        else measure_baseline(repeats=args.repeats, map_steps=args.map_steps, stress_steps=args.stress_steps)
    )
    print(
        json.dumps(
            results,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
