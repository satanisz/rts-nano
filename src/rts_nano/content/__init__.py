"""Public access to validated, Pygame-free gameplay content definitions."""

from rts_nano.content.definitions import (
    AbilityDefinition,
    AttackKind,
    BuildingDefinition,
    FactionDefinition,
    ResourceCost,
    ResourceDefinition,
    StatModifier,
    UnitDefinition,
    UpgradeDefinition,
)
from rts_nano.content.registry import (
    ABILITY_DEFINITIONS,
    BUILDING_DEFINITIONS,
    CONSTRUCTION_REFUND_RATIO,
    CONTENT,
    FACTION_DEFINITIONS,
    PRODUCTION_REFUND_RATIO,
    RESOURCE_DEFINITIONS,
    UNIT_DEFINITIONS,
    UPGRADE_DEFINITIONS,
    ContentRegistry,
)

__all__ = [
    "ABILITY_DEFINITIONS",
    "BUILDING_DEFINITIONS",
    "CONSTRUCTION_REFUND_RATIO",
    "CONTENT",
    "FACTION_DEFINITIONS",
    "PRODUCTION_REFUND_RATIO",
    "RESOURCE_DEFINITIONS",
    "UNIT_DEFINITIONS",
    "UPGRADE_DEFINITIONS",
    "AttackKind",
    "AbilityDefinition",
    "BuildingDefinition",
    "ContentRegistry",
    "FactionDefinition",
    "ResourceCost",
    "ResourceDefinition",
    "StatModifier",
    "UnitDefinition",
    "UpgradeDefinition",
]
