"""Public access to validated, Pygame-free gameplay content definitions."""

from rts_nano.content.definitions import (
    AttackKind,
    BuildingDefinition,
    FactionDefinition,
    ResourceCost,
    ResourceDefinition,
    UnitDefinition,
)
from rts_nano.content.registry import (
    BUILDING_DEFINITIONS,
    CONSTRUCTION_REFUND_RATIO,
    CONTENT,
    FACTION_DEFINITIONS,
    PRODUCTION_REFUND_RATIO,
    RESOURCE_DEFINITIONS,
    UNIT_DEFINITIONS,
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
    "AttackKind",
    "BuildingDefinition",
    "ContentRegistry",
    "FactionDefinition",
    "ResourceCost",
    "ResourceDefinition",
    "UnitDefinition",
]
