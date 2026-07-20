"""Public access to validated, Pygame-free gameplay content definitions."""

from rts_nano.content.definitions import (
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
    "BUILDING_DEFINITIONS",
    "CONSTRUCTION_REFUND_RATIO",
    "CONTENT",
    "FACTION_DEFINITIONS",
    "PRODUCTION_REFUND_RATIO",
    "RESOURCE_DEFINITIONS",
    "UNIT_DEFINITIONS",
    "UPGRADE_DEFINITIONS",
    "AttackKind",
    "BuildingDefinition",
    "ContentRegistry",
    "FactionDefinition",
    "ResourceCost",
    "ResourceDefinition",
    "StatModifier",
    "UnitDefinition",
    "UpgradeDefinition",
]
