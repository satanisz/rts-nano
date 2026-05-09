"""Tests for no-render simulation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import TeamColor
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "Blue": {"peasant": [[20, 20]], "base": [[60, 60]], "knight": [], "archer": [], "mage": []},
        "Red": {"peasant": [], "base": [[250, 250]], "knight": [], "archer": [], "mage": []},
        "Resources": {"wood": [], "cristal": []},
        "Terrain": {
            "width": 400,
            "height": 300,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def test_headless_simulation_steps_and_issues_orders() -> None:
    """Headless mode can move simulation forward without drawing."""
    simulation = HeadlessSimulation.from_settings(_settings())

    affected = simulation.issue_move_order(TeamColor.BLUE, (120, 120))
    simulation.step(3)

    assert affected == 1
    assert simulation.units_for_team(TeamColor.BLUE)[0].state == "MOVING"
    simulation.close()


def test_group_move_order_assigns_formation_slots() -> None:
    """Group movement spreads units around the clicked destination."""
    settings = _settings()
    settings["Blue"]["peasant"] = [[20, 20], [28, 20], [36, 20], [44, 20]]
    simulation = HeadlessSimulation.from_settings(settings)

    affected = simulation.issue_move_order(TeamColor.BLUE, (160, 160))
    targets = {(round(unit.target_x), round(unit.target_y)) for unit in simulation.units_for_team(TeamColor.BLUE)}

    assert affected == 4
    assert len(targets) == 4
    simulation.close()


def test_stuck_unit_skips_blocked_waypoint() -> None:
    """A moving unit can recover when collision resolution prevents progress."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    unit = simulation.units_for_team(TeamColor.BLUE)[0]
    unit.state = "MOVING"
    unit.path = [(80, 20), (120, 20)]

    for _ in range(75):
        manager._update_unit_stuck_recovery(unit)

    assert unit.path == [(120, 20)]
    simulation.close()


def test_peasant_starts_harvesting_targeted_resources() -> None:
    """A peasant can finish the final path waypoint beside a resource."""
    settings = _settings()
    settings["Resources"]["wood"] = [[100, 20]]
    settings["Resources"]["cristal"] = [[20, 100]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    peasant = manager.entities[TeamColor.BLUE].peasents[0]

    wood = manager.resources.woods[0]
    manager._assign_unit_target(peasant, wood.get_center(), wood)
    simulation.step(80)

    assert peasant.carry_wood > 0

    peasant.x, peasant.y = 20, 20
    peasant.carry_wood = 0
    peasant.state = "IDLE"
    cristal = manager.resources.cristals[0]
    manager._assign_unit_target(peasant, cristal.get_center(), cristal)
    simulation.step(80)

    assert peasant.carry_cristal > 0
    simulation.close()


def test_peasant_harvests_resource_beyond_ramp_edge() -> None:
    """A* should not choose a diagonal shortcut that local movement rejects."""
    simulation = HeadlessSimulation.from_map_file(Path("src/rts_nano/maps/map_settings_01.json"))
    manager = simulation.manager
    peasant = manager.entities[TeamColor.BLUE].peasents[0]
    crystal = manager.resources.cristals[0]

    manager._assign_unit_target(peasant, crystal.get_center(), crystal)
    simulation.step(400)

    assert peasant.carry_cristal > 0
    simulation.close()


def test_unit_path_is_not_blocked_by_neutral_resources() -> None:
    """Neutral resources are selectable targets, not pathfinding blockers."""
    simulation = HeadlessSimulation.from_map_file(Path("src/rts_nano/maps/map_settings_01.json"))
    manager = simulation.manager
    knight = manager.entities[TeamColor.BLUE].knights[0]

    manager._assign_unit_target(knight, (1000, 500))
    simulation.step(300)

    assert knight.state == "IDLE"
    assert not knight.path
    assert knight.get_center() == (1000, 500)
    simulation.close()
