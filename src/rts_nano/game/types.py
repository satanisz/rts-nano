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

UpgradeId = NewType("UpgradeId", str)
"""Stable identifier of a team-wide technology."""

ExclusivityGroupId = NewType("ExclusivityGroupId", str)
"""Stable identifier of a mutually exclusive technology choice."""


class AttackKind(StrEnum):
    """Supported deterministic attack categories."""

    MELEE = "Melee"
    RANGED = "Ranged"
    NONE = "None"


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


class ModifierStat(StrEnum):
    """Closed set of definition-backed stats that research may modify."""

    MAX_LIFE = "max_life"
    SHIELD_MAX = "shield_max"
    SHIELD_REGEN = "shield_regen"
    SHIELD_MODIFIER = "shield_modifier"
    ATTACK_DAMAGE = "attack_damage"
    ATTACK_MODIFIER = "attack_modifier"
    ATTACK_RANGE = "attack_range"
    ATTACK_SPEED = "attack_speed"
    SPEED = "speed"
    VISION_RANGE = "vision_range"
    MELEE_ATTACK_RANGE = "melee_attack_range"
    RANGED_MIN_ATTACK_RANGE = "ranged_min_attack_range"
    RANGED_ATTACK_RANGE = "ranged_attack_range"
    POISON_DAMAGE = "poison_damage"
    POISON_DURATION = "poison_duration"
    SPLASH_RADIUS = "splash_radius"


AbilityId = NewType("AbilityId", str)
"""Stable identifier of an active unit ability."""


class AbilityTargetKind(StrEnum):
    """Closed targeting modes for deterministic casts."""

    SELF = "self"
    ALLY = "ally"
    ENEMY = "enemy"
    GROUND = "ground"
    AREA = "area"


class AbilityEffectKind(StrEnum):
    """Closed effect handlers interpreted by the pure ability system."""

    DIRECT_DAMAGE = "direct_damage"
    BARRIER_PULSE = "barrier_pulse"
    ARC_BIND = "arc_bind"
    TOXIC_CLOUD = "toxic_cloud"
    MUTAGENIC_SURGE = "mutagenic_surge"
