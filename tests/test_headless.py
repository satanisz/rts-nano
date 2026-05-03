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
