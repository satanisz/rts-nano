"""Building entity implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.content import CONTENT
from rts_nano.simulation.entities.base import Building, Entity, TeamColor, init_shield

if TYPE_CHECKING:
    from rts_nano.content import BuildingDefinition
    from rts_nano.game.constants import AttackType


class Base(Building):
    """Represent the main team building used for resource drop-off.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("base"))


class Barracks(Building):
    """Represent a basic military production building."""

    def __init__(self, x: int, y: int, team: TeamColor, definition: BuildingDefinition) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, definition)


class House(Building):
    """Represent a support building that increases population capacity."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("house"))


class MageTower(Building):
    """Represent an advanced production building that trains mages."""

    def __init__(self, x: int, y: int, team: TeamColor, definition: BuildingDefinition) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, definition)


class Tower(Building):
    """Stationary defensive building that auto-attacks nearby enemies.

    The tower does not move or produce; the ``CombatSystem`` drives its ranged
    auto-attacks once construction is complete. Combat stats live here so the
    system can treat it like any other ranged attacker.
    """

    def __init__(self, x: int, y: int, team: TeamColor, definition: BuildingDefinition) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, definition)
        self.attack_damage = definition.attack_damage
        self.attack_modifier = definition.attack_modifier
        self.attack_range = definition.attack_range
        self.attack_speed = definition.attack_speed
        self.attack_type = definition.attack_kind
        self.attack_cooldown = 0
        self.poison_damage = definition.poison_damage
        self.poison_duration = definition.poison_duration
        init_shield(self, definition.shield_max, definition.shield_regen, definition.shield_regen_delay)
        self.last_attack_event: tuple[tuple[float, float], tuple[float, float], AttackType, Entity] | None = None


# --- AEGIS (Blue) military structures. Production/combat plumbing is inherited
# from Barracks/MageTower/Tower; only the spec key and tower stats differ. ---


class Arsenal(Barracks):
    """AEGIS tier-1 military building: trains Marksmen and Guardians."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("arsenal"))


class Spire(MageTower):
    """AEGIS tier-2 building: trains Arclight artillery (requires an Arsenal)."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("spire"))


class Bastion(Tower):
    """AEGIS defense: durable, long-range auto-attacking turret with a shield."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("bastion"))


# --- RUST (Red) military structures. ---


class Pit(Barracks):
    """RUST tier-1 military building: trains Rippers and Spitters."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("pit"))


class ChemVat(MageTower):
    """RUST tier-2 building: brews Brutes (requires a Pit)."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("chem_vat"))


class Spiker(Tower):
    """RUST defense: cheaper, faster-firing, shorter-range turret that poisons."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_building("spiker"))
