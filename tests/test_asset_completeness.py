"""Regression checks for runtime unit and building artwork."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rts_nano.game.assets.entities import (
    Arclight,
    Arsenal,
    Base,
    Bastion,
    Brute,
    ChemVat,
    Guardian,
    House,
    Marksman,
    Pit,
    Ripper,
    Spiker,
    Spire,
    Spitter,
    TeamColor,
)

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Building, Unit


@pytest.mark.parametrize(
    ("unit_type", "team"),
    [
        (Marksman, TeamColor.BLUE),
        (Guardian, TeamColor.BLUE),
        (Arclight, TeamColor.BLUE),
        (Ripper, TeamColor.RED),
        (Spitter, TeamColor.RED),
        (Brute, TeamColor.RED),
    ],
)
def test_faction_units_ship_runtime_art(unit_type: type[Unit], team: TeamColor) -> None:
    """Every faction unit loads a square sprite and a command-panel portrait."""
    unit = unit_type(0, 0, team)

    assert unit.image is not None
    assert unit.image.get_size() == (unit.size, unit.size)
    assert unit.avatar_image is not None
    assert unit.avatar_image.get_size() == (120, 120)


@pytest.mark.parametrize(
    ("building_type", "team"),
    [
        (Base, TeamColor.BLUE),
        (Base, TeamColor.RED),
        (House, TeamColor.BLUE),
        (Arsenal, TeamColor.BLUE),
        (Spire, TeamColor.BLUE),
        (Bastion, TeamColor.BLUE),
        (Pit, TeamColor.RED),
        (ChemVat, TeamColor.RED),
        (Spiker, TeamColor.RED),
    ],
)
def test_buildings_ship_runtime_art(building_type: type[Building], team: TeamColor) -> None:
    """Every playable building loads a square sprite and HUD portrait."""
    building = building_type(0, 0, team)

    assert building.image is not None
    assert building.image.get_size() == (building.size, building.size)
    assert building.avatar_image is not None
    assert building.avatar_image.get_size() == (120, 120)


def test_repeated_entities_share_cached_visual_surfaces() -> None:
    """Identical runtime art is decoded and scaled once, then safely shared."""
    first = Marksman(0, 0, TeamColor.BLUE)
    second = Marksman(100, 100, TeamColor.BLUE)

    assert first.original_image is second.original_image
    assert first.avatar_image is second.avatar_image
