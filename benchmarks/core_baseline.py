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

from rts_nano.game.assets.entities import TeamColor
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings

MAP_01 = Path("src/rts_nano/maps/map_settings_01.json")


def _stress_settings(unit_count: int = 400) -> MapSettings:
    """Build a large open-map scenario with evenly split, dispersed armies."""
    per_team = unit_count // 2
    blue = [[100 + (index % 20) * 70, 100 + (index // 20) * 70] for index in range(per_team)]
    red = [[3100 - (index % 20) * 70, 2000 - (index // 20) * 70] for index in range(per_team)]
    return {
        "Blue": {
            "peasant": [],
            "base": [[80, 80]],
            "guardian": blue,
            "marksman": [],
            "arclight": [],
        },
        "Red": {
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


def main() -> None:
    """Run the baseline and print machine-readable JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--map-steps", type=int, default=2000)
    parser.add_argument("--stress-steps", type=int, default=200)
    args = parser.parse_args()
    print(
        json.dumps(
            measure_baseline(repeats=args.repeats, map_steps=args.map_steps, stress_steps=args.stress_steps),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
