"""Tests for no-render simulation helpers."""

from __future__ import annotations

from rts_nano.game.assets.entities.base_entities import TeamColor
from rts_nano.headless import HeadlessSimulation
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
