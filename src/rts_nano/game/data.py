"""Compatibility facade for gameplay content during the S1 migration.

New runtime code should import :mod:`rts_nano.content` directly.  Team-to-
faction mapping and the legacy roster helpers remain here until Sprint S2.
"""

from __future__ import annotations

from rts_nano.content import (
    CONSTRUCTION_REFUND_RATIO as CONSTRUCTION_REFUND_RATIO,
)
from rts_nano.content import (
    CONTENT,
    BuildingDefinition,
    UnitDefinition,
)
from rts_nano.content import (
    PRODUCTION_REFUND_RATIO as PRODUCTION_REFUND_RATIO,
)
from rts_nano.content import (
    ResourceCost as ResourceCost,
)

UnitSpec = UnitDefinition
BuildingSpec = BuildingDefinition
UNIT_SPECS = CONTENT.units
BUILDING_SPECS = CONTENT.buildings
RESOURCE_KINDS: tuple[str, ...] = tuple(CONTENT.resources)

FACTION_BY_TEAM: dict[str, str] = {"Blue": "AEGIS", "Red": "RUST"}


def faction_for_team(team: object) -> str:
    """Return the faction a team plays (Blue=AEGIS, Red=RUST), else ``any``."""
    team_name = str(getattr(team, "value", team))
    return FACTION_BY_TEAM.get(team_name, "any")


def units_for_faction(faction: str) -> dict[str, UnitDefinition]:
    """Return the registry roster, preserving the legacy unknown-team fallback."""
    if faction not in CONTENT.factions:
        return {key: value for key, value in CONTENT.units.items() if value.faction is None}
    return CONTENT.units_for_faction(faction)


def buildings_for_faction(faction: str) -> dict[str, BuildingDefinition]:
    """Return the registry roster, preserving the legacy unknown-team fallback."""
    if faction not in CONTENT.factions:
        return {key: value for key, value in CONTENT.buildings.items() if value.faction is None}
    return CONTENT.buildings_for_faction(faction)


def get_unit_spec(unit_type: str) -> UnitDefinition:
    """Compatibility wrapper around the central content registry."""
    return CONTENT.get_unit(unit_type)


def get_building_spec(building_type: str) -> BuildingDefinition:
    """Compatibility wrapper around the central content registry."""
    return CONTENT.get_building(building_type)
