"""Regression checks for runtime unit and building artwork."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rts_nano.game.ui.pygame_assets import PygameAssets
from rts_nano.simulation.entities import (
    Arclight,
    Arsenal,
    Base,
    Bastion,
    Brute,
    ChemVat,
    Gold,
    Guardian,
    House,
    Marksman,
    Pit,
    Ripper,
    Spiker,
    Spire,
    Spitter,
    TeamColor,
    Wood,
)

if TYPE_CHECKING:
    from rts_nano.simulation.entities.base import Building, Unit


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
    """Presentation resolves a square sprite and portrait for every faction unit."""
    unit = unit_type(0, 0, team)
    assets = PygameAssets()
    sprite = assets.sprite(unit)
    portrait = assets.portrait(unit)

    assert sprite is not None
    assert sprite.get_size() == (unit.size, unit.size)
    assert portrait is not None
    assert portrait.get_size() == (120, 120)


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
    """Presentation resolves a square sprite and portrait for every building."""
    building = building_type(0, 0, team)
    assets = PygameAssets()
    sprite = assets.sprite(building)
    portrait = assets.portrait(building)

    assert sprite is not None
    assert sprite.get_size() == (building.size, building.size)
    assert portrait is not None
    assert portrait.get_size() == (120, 120)


def test_repeated_entities_share_cached_visual_surfaces() -> None:
    """The presentation cache shares both normal and flipped variants."""
    first = Marksman(0, 0, TeamColor.BLUE)
    second = Marksman(100, 100, TeamColor.BLUE)
    assets = PygameAssets()

    assert assets.sprite(first) is assets.sprite(second)
    assert assets.sprite(first, flipped=True) is assets.sprite(second, flipped=True)
    assert assets.portrait(first) is assets.portrait(second)


@pytest.mark.parametrize("resource_type", [Wood, Gold])
def test_resources_ship_runtime_art(resource_type: type) -> None:
    """Presentation resolves world and portrait art for neutral resources."""
    resource = resource_type(0, 0)
    assets = PygameAssets()

    assert assets.sprite(resource) is not None
    assert assets.portrait(resource) is not None
