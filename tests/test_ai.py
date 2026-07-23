"""Integration tests for the scripted AI opponent.

These exercise the full economy/construction/production/combat loop through the
same public manager API the AI uses, so they double as end-to-end checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.ai import ScriptedAI
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities.base import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _ai_settings() -> MapSettings:
    wood = [[200 + 10 * i, 120] for i in range(6)]
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [],
            "base": [[700, 400]],
            "guardian": [],
            "marksman": [],
            "arclight": [],
        },
        "Red": {
            "faction_id": "RUST",
            "peasant": [[120, 120], [150, 120], [120, 150]],
            "base": [[120, 90]],
            "ripper": [],
            "spitter": [],
            "brute": [],
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
    red = manager.teams[TeamColor.RED]
    ai = ScriptedAI(manager, TeamColor.RED, decision_interval=10)
    initial_wood = sum(node.amount for node in manager.state.resources_by_content("wood"))

    assert red.resources["wood"] == 0
    for _ in range(600):
        ai.step()
        simulation.step(1)

    remaining_wood = sum(node.amount for node in manager.state.resources_by_content("wood"))
    assert remaining_wood < initial_wood
    assert red.resources["wood"] > 0 or manager.state.entities_by_content_id("pit", team=TeamColor.RED)
    simulation.close()


def test_scripted_ai_builds_trains_and_attacks() -> None:
    """With resources the RUST AI raises a pit, trains units, scouts, and attacks."""
    simulation = HeadlessSimulation.from_settings(_ai_settings())
    manager = simulation.manager
    red = manager.teams[TeamColor.RED]
    red.resources.update({"wood": 600, "gold": 300})
    ai = ScriptedAI(manager, TeamColor.RED, decision_interval=10)

    built_pit = trained_unit = launched_attack = False
    for _ in range(1500):
        ai.step()
        simulation.step(1)
        pits = manager.state.entities_by_content_id("pit", team=TeamColor.RED)
        rippers = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)
        if pits and not pits[0].is_under_construction:
            built_pit = True
        if rippers:
            trained_unit = True
        if any(unit.attack_move_destination is not None for unit in rippers):
            launched_attack = True
        if built_pit and trained_unit and launched_attack:
            break

    assert built_pit
    assert trained_unit
    assert launched_attack
    simulation.close()


def test_scripted_ai_does_not_know_hidden_enemy_base() -> None:
    """A hidden base cannot become an attack target through omniscient state access."""
    settings = _ai_settings()
    settings["Red"]["ripper"] = [[140, 200], [170, 200], [200, 200]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    ai = ScriptedAI(manager, TeamColor.RED, decision_interval=1)
    enemy_base = manager.bases_for_team(TeamColor.BLUE)[0]

    ai.step()

    rippers = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)
    scouting = [unit for unit in rippers if unit.attack_move_destination is not None]
    assert ai.known_enemy_base_position is None
    assert len(scouting) == 1
    assert scouting[0].attack_move_destination != enemy_base.get_center()
    simulation.close()


def test_scripted_ai_attacks_base_after_legitimate_sighting() -> None:
    """Once team vision reaches the enemy Base, its observed position becomes actionable."""
    settings = _ai_settings()
    settings["Blue"]["base"] = [[430, 120]]
    settings["Red"]["ripper"] = [[140, 200], [170, 200], [200, 200]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    ai = ScriptedAI(manager, TeamColor.RED, decision_interval=1)
    enemy_position = manager.bases_for_team(TeamColor.BLUE)[0].get_center()

    ai.step()

    rippers = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)
    assert ai.known_enemy_base_position == enemy_position
    assert all(unit.attack_move_destination == enemy_position for unit in rippers)
    simulation.close()


def test_scripted_ai_ignores_undiscovered_resource_nodes() -> None:
    """Workers may use visible or remembered resources, but not hidden map-state nodes."""
    settings = _ai_settings()
    settings["Resources"] = {"wood": [[760, 560]], "gold": []}
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    ai = ScriptedAI(manager, TeamColor.RED, decision_interval=1)

    ai.step()

    assert all(
        peasant.state == "IDLE" for peasant in manager.state.entities_by_content_id("peasant", team=TeamColor.RED)
    )
    simulation.close()
