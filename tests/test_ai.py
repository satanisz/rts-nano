"""Integration tests for the scripted AI opponent.

These exercise the full economy/construction/production/combat loop through the
same public manager API the AI uses, so they double as end-to-end checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.ai import ScriptedAI
from rts_nano.game.assets.entities.base_entities import TeamColor
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _ai_settings() -> MapSettings:
    wood = [[200 + 10 * i, 120] for i in range(6)]
    return {
        "Blue": {"peasant": [], "base": [[700, 400]], "knight": [], "archer": [], "mage": []},
        "Red": {
            "peasant": [[120, 120], [150, 120], [120, 150]],
            "base": [[120, 90]],
            "knight": [],
            "archer": [],
            "mage": [],
        },
        "Resources": {"wood": wood, "gold": [[200, 170], [210, 170]]},
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


def test_scripted_ai_gathers_resources_into_bank() -> None:
    """The AI drives idle workers to harvest and bank resources."""
    simulation = HeadlessSimulation.from_settings(_ai_settings())
    manager = simulation.manager
    red = manager.entities[TeamColor.RED]
    ai = ScriptedAI(manager, TeamColor.RED, decision_interval=10)

    assert red.resources["wood"] == 0
    for _ in range(600):
        ai.step()
        simulation.step(1)

    assert red.resources["wood"] > 0
    simulation.close()


def test_scripted_ai_builds_trains_and_attacks() -> None:
    """With resources available the AI builds a barracks, trains knights, and attacks."""
    simulation = HeadlessSimulation.from_settings(_ai_settings())
    manager = simulation.manager
    red = manager.entities[TeamColor.RED]
    red.resources.update({"wood": 600, "gold": 300})
    ai = ScriptedAI(manager, TeamColor.RED, decision_interval=10)

    built_barracks = trained_knight = launched_attack = False
    for _ in range(1500):
        ai.step()
        simulation.step(1)
        if red.barracks and not red.barracks[0].is_under_construction:
            built_barracks = True
        if red.knights:
            trained_knight = True
        if any(knight.attack_move_destination is not None for knight in red.knights):
            launched_attack = True
        if built_barracks and trained_knight and launched_attack:
            break

    assert built_barracks
    assert trained_knight
    assert launched_attack
    simulation.close()
