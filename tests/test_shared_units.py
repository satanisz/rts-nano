"""Shared Knight, Archer, and Mage content is usable by both factions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rts_nano.content import CONTENT
from rts_nano.headless import HeadlessSimulation
from rts_nano.map_schema import validate_map_settings
from rts_nano.simulation.entities import Archer, Knight, Mage, TeamColor
from rts_nano.simulation.entities.base import Building

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings
    from rts_nano.simulation.entities.base import Unit


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "base": [[100, 100]],
            "arsenal": [[220, 100]],
            "spire": [[340, 100]],
        },
        "Red": {
            "faction_id": "RUST",
            "base": [[700, 500]],
            "pit": [[580, 500]],
            "chem_vat": [[460, 500]],
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


@pytest.mark.parametrize(
    ("producer_id", "team", "unit_id", "unit_type"),
    [
        ("arsenal", TeamColor.BLUE, "knight", Knight),
        ("pit", TeamColor.RED, "knight", Knight),
        ("arsenal", TeamColor.BLUE, "archer", Archer),
        ("pit", TeamColor.RED, "archer", Archer),
        ("spire", TeamColor.BLUE, "mage", Mage),
        ("chem_vat", TeamColor.RED, "mage", Mage),
    ],
)
def test_both_factions_train_shared_units(
    producer_id: str,
    team: TeamColor,
    unit_id: str,
    unit_type: type[Unit],
) -> None:
    """Every shared unit completes from both canonical faction producers."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    manager.teams[team].resources.update({"wood": 1000, "gold": 1000})
    producer = manager.state.entities_by_content_id(producer_id, team=team)[0]
    assert isinstance(producer, Building)

    assert manager.produce_unit(producer, unit_id)
    simulation.step(CONTENT.get_unit(unit_id).production_frames)

    trained = manager.state.entities_by_content_id(unit_id, team=team)
    assert len(trained) == 1
    assert isinstance(trained[0], unit_type)
    simulation.close()


def test_map_schema_accepts_shared_units_for_both_factions() -> None:
    """Shared concrete IDs are legal in either faction's serialized army."""
    settings = _settings()
    for team_name in ("Blue", "Red"):
        settings[team_name]["knight"] = [[300, 300]]
        settings[team_name]["archer"] = [[350, 300]]
        settings[team_name]["mage"] = [[400, 300]]

    assert validate_map_settings(settings) == []


def test_shared_unit_uses_existing_producer_rally() -> None:
    """Shared content receives the same deterministic rally handoff as faction units."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    manager.teams[TeamColor.BLUE].resources.update({"wood": 1000, "gold": 1000})
    producer = manager.state.entities_by_content_id("arsenal", team=TeamColor.BLUE)[0]
    assert isinstance(producer, Building)

    assert manager.set_producer_rally(TeamColor.BLUE, (400, 200), [producer]) == 1
    assert manager.produce_unit(producer, "knight")
    simulation.step(CONTENT.get_unit("knight").production_frames)

    knight = manager.state.entities_by_content_id("knight", team=TeamColor.BLUE)[0]
    assert knight.current_order is not None
    assert knight.current_order.kind == "move"
    assert knight.current_order.destination == (400, 200)
    simulation.close()


def test_shared_unit_definitions_are_neutral_and_have_two_producers() -> None:
    """Shared content stays canonical while buildings provide faction access."""
    expected = {
        "knight": ("arsenal", "pit"),
        "archer": ("arsenal", "pit"),
        "mage": ("chem_vat", "spire"),
    }
    for unit_id, producer_ids in expected.items():
        assert CONTENT.get_unit(unit_id).faction is None
        assert tuple(str(item.id) for item in CONTENT.producers_for_unit(unit_id)) == producer_ids
