"""Pure immutable definitions for all gameplay content."""

from __future__ import annotations

from dataclasses import dataclass

from rts_nano.game.types import AttackKind, ContentId, EntityCategory, FactionId


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
    produced_at: ContentId
    requires: tuple[ContentId, ...]
    legacy_roster: str
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

    @property
    def key(self) -> str:
        """Compatibility name used by existing production code during S1."""
        return str(self.id)

    @property
    def roster_attribute(self) -> str:
        """Temporary S1 compatibility field removed with legacy rosters in S2."""
        return self.legacy_roster

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
