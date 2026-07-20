"""Pure immutable definitions for all gameplay content."""

from __future__ import annotations

from dataclasses import dataclass

from rts_nano.game.types import (
    AbilityEffectKind,
    AbilityId,
    AbilityTargetKind,
    AttackKind,
    ContentId,
    EntityCategory,
    ExclusivityGroupId,
    FactionId,
    ModifierStat,
    UpgradeId,
)


@dataclass(frozen=True, slots=True)
class ResourceCost:
    """Resource cost paid from a team economy bank."""

    wood: int = 0
    gold: int = 0


@dataclass(frozen=True, slots=True)
class UnitDefinition:
    """Complete gameplay definition of one trainable unit type."""

    id: ContentId
    display_name: str
    role: str
    faction: FactionId | None
    visual_key: str
    behavior: str
    cost: ResourceCost
    production_frames: int
    population: int
    requires: tuple[ContentId, ...]
    size: int
    radius: float
    speed: float
    max_carry: int
    max_life: int
    vision_range: int
    attack_damage: int
    attack_modifier: int
    attack_range: int
    attack_speed: float
    attack_kinds: tuple[AttackKind, ...]
    shield_modifier: int = 0
    shield_max: int = 0
    shield_regen: int = 0
    shield_regen_delay: int = 0
    poison_damage: int = 0
    poison_duration: int = 0
    frenzy: bool = False
    frenzy_health_fraction: float = 0.5
    frenzy_cooldown_multiplier: float = 0.66
    melee_attack_range: int = 0
    ranged_min_attack_range: int = 0
    ranged_attack_range: int = 0
    splash_radius: int = 0
    build_rate: int = 0
    repair_rate: int = 0
    energy_max: int = 0
    energy_regen_numerator: int = 0
    energy_regen_denominator: int = 1

    @property
    def key(self) -> str:
        """Compatibility name used by existing production code during S1."""
        return str(self.id)

    @property
    def category(self) -> EntityCategory:
        """Return the generic runtime category."""
        return EntityCategory.UNIT


@dataclass(frozen=True, slots=True)
class BuildingDefinition:
    """Complete gameplay definition of one constructable building type."""

    id: ContentId
    display_name: str
    role: str
    faction: FactionId | None
    visual_key: str
    behavior: str
    cost: ResourceCost
    build_frames: int
    constructable: bool
    footprint: tuple[int, int]
    size: int
    radius: float
    max_life: int
    vision_range: int
    provides_population: int = 0
    produces: tuple[ContentId, ...] = ()
    requires: tuple[ContentId, ...] = ()
    shield_modifier: int = 0
    attack_damage: int = 0
    attack_modifier: int = 0
    attack_range: int = 0
    attack_speed: float = 0.0
    attack_kind: AttackKind = AttackKind.NONE
    shield_max: int = 0
    shield_regen: int = 0
    shield_regen_delay: int = 0
    poison_damage: int = 0
    poison_duration: int = 0
    repair_hp_per_wood: int = 10

    @property
    def key(self) -> str:
        """Compatibility name used by existing construction code during S1."""
        return str(self.id)

    @property
    def category(self) -> EntityCategory:
        """Return the generic runtime category."""
        return EntityCategory.BUILDING


@dataclass(frozen=True, slots=True)
class ResourceDefinition:
    """Complete gameplay definition of one neutral resource type."""

    id: ContentId
    display_name: str
    visual_key: str
    amount: int
    size: int
    radius: float

    @property
    def key(self) -> str:
        """Return the serialized content key."""
        return str(self.id)

    @property
    def category(self) -> EntityCategory:
        """Return the generic runtime category."""
        return EntityCategory.RESOURCE


@dataclass(frozen=True, slots=True)
class FactionDefinition:
    """Explicit roster of content available to one faction."""

    id: FactionId
    display_name: str
    unit_ids: tuple[ContentId, ...]
    building_ids: tuple[ContentId, ...]


@dataclass(frozen=True, slots=True)
class StatModifier:
    """One canonical flat and rational modification of a definition stat."""

    stat: ModifierStat
    add: int = 0
    numerator: int = 1
    denominator: int = 1


@dataclass(frozen=True, slots=True)
class UpgradeDefinition:
    """Immutable team-wide research definition."""

    id: UpgradeId
    display_name: str
    description: str
    faction: FactionId
    research_at: tuple[ContentId, ...]
    cost: ResourceCost
    research_frames: int
    required_buildings: tuple[ContentId, ...] = ()
    required_upgrades: tuple[UpgradeId, ...] = ()
    exclusive_group: ExclusivityGroupId | None = None
    conflicts: tuple[UpgradeId, ...] = ()
    affected_content: tuple[ContentId, ...] = ()
    modifiers: tuple[StatModifier, ...] = ()
    granted_behaviors: tuple[str, ...] = ()
    granted_abilities: tuple[AbilityId, ...] = ()


@dataclass(frozen=True, slots=True)
class AbilityDefinition:
    """Immutable deterministic active-ability definition."""

    id: AbilityId
    display_name: str
    description: str
    target_kind: AbilityTargetKind
    effect_kind: AbilityEffectKind
    energy_cost: int
    cooldown_frames: int
    cast_range: int
    duration_frames: int = 0
    radius: int = 0
    max_targets: int = 1
    magnitude: int = 0
