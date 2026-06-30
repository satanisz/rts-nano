"""Building entity implementations."""

from pathlib import Path

from rts_nano.game.assets.entities.base_entities import Building, Entity, TeamColor, init_shield
from rts_nano.game.assets.entities.units import AEGIS_SHIELD_REGEN, AEGIS_SHIELD_REGEN_DELAY
from rts_nano.game.constants import AttackType

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Base(Building):
    """Represent the main team building used for resource drop-off.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "base"
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / f"{team.value.lower()}_base.png"),
            str(BASE_DIR / "assets" / "portraits" / "base.png"),
        )


class Barracks(Building):
    """Represent a basic military production building."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "barracks"


class House(Building):
    """Represent a support building that increases population capacity."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "house"


class MageTower(Building):
    """Represent an advanced production building that trains mages."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "mage_tower"


class Tower(Building):
    """Stationary defensive building that auto-attacks nearby enemies.

    The tower does not move or produce; the ``CombatSystem`` drives its ranged
    auto-attacks once construction is complete. Combat stats live here so the
    system can treat it like any other ranged attacker.
    """

    SIZE = 56
    RADIUS = 18.0
    MAX_LIFE = 300
    DEFAULT_ATTACK_DAMAGE = 12
    DEFAULT_ATTACK_RANGE = 180
    DEFAULT_ATTACK_SPEED = 1.0
    DEFAULT_SHIELD_MAX = 0
    DEFAULT_SHIELD_REGEN = 0
    DEFAULT_SHIELD_REGEN_DELAY = 0
    POISON_DAMAGE = 0
    POISON_DURATION = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "tower"
        self.attack_damage = self.DEFAULT_ATTACK_DAMAGE
        self.attack_modifier = 0
        self.attack_range = self.DEFAULT_ATTACK_RANGE
        self.attack_speed = self.DEFAULT_ATTACK_SPEED
        self.attack_type = AttackType.RANGED
        self.attack_cooldown = 0
        self.poison_damage = self.POISON_DAMAGE
        self.poison_duration = self.POISON_DURATION
        init_shield(self, self.DEFAULT_SHIELD_MAX, self.DEFAULT_SHIELD_REGEN, self.DEFAULT_SHIELD_REGEN_DELAY)
        self.last_attack_event: tuple[tuple[float, float], tuple[float, float], AttackType, Entity] | None = None


# --- AEGIS (Blue) military structures. Production/combat plumbing is inherited
# from Barracks/MageTower/Tower; only the spec key and tower stats differ. ---


class Arsenal(Barracks):
    """AEGIS tier-1 military building: trains Marksmen and Guardians."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "arsenal"


class Spire(MageTower):
    """AEGIS tier-2 building: trains Arclight artillery (requires an Arsenal)."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "spire"


class Bastion(Tower):
    """AEGIS defense: durable, long-range auto-attacking turret with a shield."""

    MAX_LIFE = 350
    DEFAULT_ATTACK_DAMAGE = 12
    DEFAULT_ATTACK_RANGE = 200
    DEFAULT_ATTACK_SPEED = 1.0
    DEFAULT_SHIELD_MAX = 80
    DEFAULT_SHIELD_REGEN = AEGIS_SHIELD_REGEN
    DEFAULT_SHIELD_REGEN_DELAY = AEGIS_SHIELD_REGEN_DELAY

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "bastion"


# --- RUST (Red) military structures. ---


class Pit(Barracks):
    """RUST tier-1 military building: trains Rippers and Spitters."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "pit"


class ChemVat(MageTower):
    """RUST tier-2 building: brews Brutes (requires a Pit)."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "chem_vat"


class Spiker(Tower):
    """RUST defense: cheaper, faster-firing, shorter-range turret that poisons."""

    MAX_LIFE = 250
    DEFAULT_ATTACK_DAMAGE = 8
    DEFAULT_ATTACK_RANGE = 150
    DEFAULT_ATTACK_SPEED = 0.625
    POISON_DAMAGE = 2
    POISON_DURATION = 90

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "spiker"
