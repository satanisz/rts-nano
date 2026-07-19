"""Stable domain vocabulary for content and simulation identity."""

from enum import StrEnum
from typing import NewType

ContentId = NewType("ContentId", str)
"""Stable identifier of a unit, building, or resource definition."""

EntityId = NewType("EntityId", int)
"""Stable identity of one runtime entity within a simulation."""

TeamId = NewType("TeamId", str)
"""Stable team identity independent of presentation color."""

FactionId = NewType("FactionId", str)
"""Stable faction identity assigned explicitly to a team."""


class EntityCategory(StrEnum):
    """Top-level entity categories used by generic world indexes."""

    UNIT = "unit"
    BUILDING = "building"
    RESOURCE = "resource"


class CombatRole(StrEnum):
    """Current gameplay roles used to describe combat behavior."""

    WORKER = "worker"
    MELEE = "melee"
    RANGED = "ranged"
    ARTILLERY = "artillery"
    DEFENSE = "defense"
