"""Table-driven coverage for the central gameplay content registry."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import pytest

from rts_nano.content import (
    BUILDING_DEFINITIONS,
    CONTENT,
    FACTION_DEFINITIONS,
    RESOURCE_DEFINITIONS,
    UNIT_DEFINITIONS,
    BuildingDefinition,
    ContentRegistry,
    FactionDefinition,
    ResourceDefinition,
    UnitDefinition,
)
from rts_nano.game.assets.entities import (
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
    Peasant,
    Pit,
    Ripper,
    Spiker,
    Spire,
    Spitter,
    TeamColor,
    Wood,
)
from rts_nano.game.assets.entities.base_entities import visual_assets_enabled
from rts_nano.game.types import ContentId

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def _registry(
    *,
    units: Iterable[UnitDefinition] = UNIT_DEFINITIONS,
    buildings: Iterable[BuildingDefinition] = BUILDING_DEFINITIONS,
    resources: Iterable[ResourceDefinition] = RESOURCE_DEFINITIONS,
    factions: Iterable[FactionDefinition] = FACTION_DEFINITIONS,
) -> ContentRegistry:
    return ContentRegistry(units=units, buildings=buildings, resources=resources, factions=factions)


@pytest.mark.parametrize(
    ("content_id", "factory"),
    [
        ("peasant", Peasant),
        ("marksman", Marksman),
        ("guardian", Guardian),
        ("arclight", Arclight),
        ("ripper", Ripper),
        ("spitter", Spitter),
        ("brute", Brute),
    ],
)
def test_runtime_units_get_all_stats_from_registry(content_id: str, factory: type) -> None:
    """Every concrete unit instance mirrors its immutable definition."""
    definition = CONTENT.get_unit(content_id)
    with visual_assets_enabled(False):
        unit = factory(100, 100, TeamColor.BLUE)

    assert unit.definition is definition
    assert (unit.size, unit.radius, unit.speed) == (definition.size, definition.radius, definition.speed)
    assert (unit.max_life, unit.attack_damage, unit.attack_range) == (
        definition.max_life,
        definition.attack_damage,
        definition.attack_range,
    )
    assert (unit.shield_max, unit.poison_damage, unit.splash_radius) == (
        definition.shield_max,
        definition.poison_damage,
        definition.splash_radius,
    )


@pytest.mark.parametrize(
    ("content_id", "factory"),
    [
        ("base", Base),
        ("house", House),
        ("arsenal", Arsenal),
        ("spire", Spire),
        ("bastion", Bastion),
        ("pit", Pit),
        ("chem_vat", ChemVat),
        ("spiker", Spiker),
    ],
)
def test_runtime_buildings_get_all_stats_from_registry(content_id: str, factory: type) -> None:
    """Every concrete building instance mirrors its immutable definition."""
    definition = CONTENT.get_building(content_id)
    with visual_assets_enabled(False):
        building = factory(100, 100, TeamColor.BLUE)

    assert building.definition is definition
    assert (building.size, building.radius, building.max_life) == (
        definition.size,
        definition.radius,
        definition.max_life,
    )
    assert getattr(building, "attack_damage", 0) == definition.attack_damage
    assert building.shield_max == definition.shield_max


@pytest.mark.parametrize(("content_id", "factory"), [("wood", Wood), ("gold", Gold)])
def test_runtime_resources_get_all_stats_from_registry(content_id: str, factory: type) -> None:
    """Resource nodes use registry amount and geometry."""
    definition = CONTENT.get_resource(content_id)
    with visual_assets_enabled(False):
        resource = factory(100, 100)
    assert resource.definition is definition
    assert (resource.amount, resource.size, resource.radius) == (
        definition.amount,
        definition.size,
        definition.radius,
    )


def test_registry_indexes_are_read_only() -> None:
    """Callers cannot mutate the canonical content mappings."""
    with pytest.raises(TypeError):
        CONTENT.units["peasant"] = CONTENT.get_unit("peasant")  # type: ignore[index]


@pytest.mark.parametrize(
    "broken_registry",
    [
        lambda: _registry(units=(*UNIT_DEFINITIONS, UNIT_DEFINITIONS[0])),
        lambda: _registry(resources=(replace(RESOURCE_DEFINITIONS[0], id=ContentId("peasant")),)),
        lambda: _registry(
            units=(replace(UNIT_DEFINITIONS[0], produced_at=ContentId("missing")), *UNIT_DEFINITIONS[1:])
        ),
        lambda: _registry(resources=(replace(RESOURCE_DEFINITIONS[0], amount=0), RESOURCE_DEFINITIONS[1])),
        lambda: _registry(
            buildings=(
                *BUILDING_DEFINITIONS[:2],
                replace(BUILDING_DEFINITIONS[2], requires=(ContentId("spire"),)),
                replace(BUILDING_DEFINITIONS[3], requires=(ContentId("arsenal"),)),
                *BUILDING_DEFINITIONS[4:],
            )
        ),
        lambda: _registry(
            factions=(
                replace(FACTION_DEFINITIONS[0], unit_ids=(*FACTION_DEFINITIONS[0].unit_ids, ContentId("ripper"))),
                FACTION_DEFINITIONS[1],
            )
        ),
    ],
)
def test_registry_rejects_invalid_content_graphs(broken_registry: Callable[[], ContentRegistry]) -> None:
    """Invalid IDs, values, links, cycles, and faction rosters fail at startup."""
    with pytest.raises(ValueError, match="."):
        broken_registry()
