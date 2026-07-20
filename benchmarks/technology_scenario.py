"""Repeatable headless benchmark with completed faction doctrines and active Mage effects."""

from __future__ import annotations

import json
import time
from typing import cast

from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import Mage, TeamColor


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run() -> dict[str, float | int]:
    """Measure an active-effect window followed by a longer upgraded idle match."""
    simulation = HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {
                "faction_id": "AEGIS",
                "base": [[100, 100]],
                "arsenal": [[170, 100]],
                "spire": [[240, 100]],
                "knight": [[280 + index * 8, 280] for index in range(10)],
                "archer": [[280 + index * 8, 240] for index in range(10)],
                "mage": [[330, 320]],
            },
            "Red": {
                "faction_id": "RUST",
                "base": [[700, 500]],
                "pit": [[630, 500]],
                "chem_vat": [[560, 500]],
                "knight": [[430 + index * 8, 280] for index in range(10)],
                "archer": [[430 + index * 8, 240] for index in range(10)],
                "mage": [[400, 320]],
            },
            "Resources": {"wood": [], "gold": []},
            "Terrain": {
                "width": 800,
                "height": 600,
                "high_ground": [],
                "water": [],
                "ramps": [],
                "rocks": [],
                "grass": [],
            },
        }
    )
    manager = simulation.manager
    for upgrade_id in (
        "aegis_knight_bulwark",
        "aegis_archer_arcshot",
        "aegis_mage_arcbinder",
        "aegis_arc_targeting",
    ):
        _require(manager.upgrades.complete(TeamColor.BLUE, upgrade_id), f"failed upgrade: {upgrade_id}")
    for upgrade_id in (
        "rust_knight_pack",
        "rust_archer_venom",
        "rust_mage_plaguecaller",
        "rust_advanced_mutations",
        "rust_concentrated_toxins",
    ):
        _require(manager.upgrades.complete(TeamColor.RED, upgrade_id), f"failed upgrade: {upgrade_id}")
    blue_mage = cast("Mage", manager.state.entities_by_content_id("mage", team=TeamColor.BLUE)[0])
    red_mage = cast("Mage", manager.state.entities_by_content_id("mage", team=TeamColor.RED)[0])
    red_knight = manager.state.entities_by_content_id("knight", team=TeamColor.RED)[0]
    _require(
        manager.issue_cast_order(TeamColor.BLUE, "arc_bind", blue_mage, target=red_knight) == 1,
        "failed AEGIS cast",
    )
    _require(
        manager.issue_cast_order(TeamColor.RED, "toxic_cloud", red_mage, destination=(320, 260)) == 1,
        "failed RUST cast",
    )

    active_steps = 120
    started = time.perf_counter()
    simulation.step(active_steps)
    active_elapsed = time.perf_counter() - started
    long_steps = 5000
    started = time.perf_counter()
    simulation.step(long_steps)
    long_elapsed = time.perf_counter() - started
    simulation.close()
    return {
        "active_effect_steps": active_steps,
        "active_effect_steps_per_second": round(active_steps / active_elapsed, 3),
        "long_match_steps": long_steps,
        "long_match_steps_per_second": round(long_steps / long_elapsed, 3),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
