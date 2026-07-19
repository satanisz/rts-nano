"""Generic entity-store and explicit faction-model tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities import TeamColor
from rts_nano.game.types import EntityCategory
from rts_nano.headless import HeadlessSimulation
from rts_nano.map_schema import validate_map_settings

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings(blue_faction: str = "RUST", red_faction: str = "AEGIS") -> MapSettings:
    blue_army = {"ripper": [[120, 120]]} if blue_faction == "RUST" else {"guardian": [[120, 120]]}
    red_army = {"ripper": [[680, 480]]} if red_faction == "RUST" else {"guardian": [[680, 480]]}
    return {
        "schema_version": 2,
        "Blue": {"faction_id": blue_faction, "peasant": [[80, 80]], "base": [[80, 140]], **blue_army},
        "Red": {"faction_id": red_faction, "peasant": [[720, 520]], "base": [[720, 460]], **red_army},
        "Resources": {"wood": [[400, 300]], "gold": []},
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


def test_store_assigns_stable_ids_and_consistent_indexes() -> None:
    """Primary IDs and team/category/content indexes refer to the same entities."""
    simulation = HeadlessSimulation.from_settings(_settings())
    state = simulation.manager.state
    all_entities = state.all_entities

    assert [entity.entity_id for entity in all_entities] == list(range(1, len(all_entities) + 1))
    assert state.store.by_category(EntityCategory.UNIT, team=TeamColor.BLUE) == state.units_for_team(TeamColor.BLUE)
    assert state.store.by_content_id("ripper", team=TeamColor.BLUE)[0] in state.units_for_team(TeamColor.BLUE)

    removed = state.store.by_content_id("wood")[0]
    assert state.store.remove(removed) is True
    assert removed not in state.all_entities
    assert state.store.by_content_id("wood") == []
    simulation.close()


def test_team_color_does_not_choose_faction() -> None:
    """Blue can run RUST while Red runs AEGIS without code or content changes."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager

    assert manager.state.faction_for_team(TeamColor.BLUE) == "RUST"
    assert manager.state.faction_for_team(TeamColor.RED) == "AEGIS"
    assert manager.state.entities_by_content_id("ripper", team=TeamColor.BLUE)
    assert manager.state.entities_by_content_id("guardian", team=TeamColor.RED)
    assert manager.construction.can_team_construct(TeamColor.BLUE, "pit")[0] is False  # no resources
    assert manager.construction.can_team_construct(TeamColor.BLUE, "arsenal") == (False, "wrong_faction")
    simulation.close()


def test_two_teams_can_use_the_same_faction() -> None:
    """Faction ownership is independent for each team and may be shared."""
    simulation = HeadlessSimulation.from_settings(_settings("AEGIS", "AEGIS"))
    manager = simulation.manager
    manager.teams[TeamColor.BLUE].resources.update({"wood": 220, "gold": 60})
    manager.teams[TeamColor.RED].resources.update({"wood": 220, "gold": 60})

    assert manager.state.faction_for_team(TeamColor.BLUE) == "AEGIS"
    assert manager.state.faction_for_team(TeamColor.RED) == "AEGIS"
    assert manager.construction.can_team_construct(TeamColor.BLUE, "arsenal") == (True, None)
    assert manager.construction.can_team_construct(TeamColor.RED, "arsenal") == (True, None)
    simulation.close()


def test_map_validator_rejects_content_from_another_faction() -> None:
    """Explicit faction rosters are enforced by the versioned map schema."""
    payload = _settings("AEGIS", "RUST")
    payload["Blue"]["ripper"] = [[200, 200]]

    assert "Blue.ripper is not available to faction AEGIS." in validate_map_settings(payload)
