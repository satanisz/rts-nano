"""Concrete unit classes and their special combat/interaction rules.

All units inherit the movement and base combat state machine from ``Unit``.
Concrete classes mainly provide balance constants, sprites, and small behavior
overrides. When adding a new unit type, also register it in
``manager.EntityFactory`` and consider whether the map editor should expose a
placement tool.
"""

from pathlib import Path

from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, TeamColor, Unit
from rts_nano.game.constants import AttackType
from rts_nano.game.rules import calculate_height_range_bonus, distance_between

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Peasant(Unit):
    """Worker unit that can gather resources and deposit them at allied bases.

    Peasants enter ``GATHERING`` after reaching a ``Resource`` target and
    ``DEPOSITING`` after reaching an allied ``Building``. The manager performs
    the actual resource transfer because it owns team resource banks.
    """

    SIZE = 30
    RADIUS = 10.0
    DEFAULT_SPEED = 2.0
    DEFAULT_MAX_CARRY = 10
    DEFAULT_MAX_LIFE = 5
    DEFAULT_ATTACK_DAMAGE = 3
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 0
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.MELEE,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_peasant.png"))

    def _handle_target_reached(self) -> None:
        """Transition the peasant to gathering or depositing when appropriate."""
        if self.target_entity:
            if isinstance(self.target_entity, Resource):
                self.state = "GATHERING"
            elif isinstance(self.target_entity, Building) and self.target_entity.team == self.team:
                self.state = "DEPOSITING"
            elif self._is_hostile_target(self.target_entity):
                self.state = "ATTACKING"
            else:
                self.state = "IDLE"
            return

        self.state = "IDLE"


class Knight(Unit):
    """Frontline melee unit."""

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 2.5
    DEFAULT_MAX_CARRY = 3
    DEFAULT_MAX_LIFE = 100
    DEFAULT_ATTACK_DAMAGE = 10
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 5
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.MELEE,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_knight.png"))

    def _attack(self, target: Entity) -> None:
        """Perform a melee attack."""
        if self.attack_type != AttackType.MELEE:
            self.state = "IDLE"
            return
        super()._attack(target)


class Archer(Unit):
    """Ranged unit with a dead-zone and melee fallback.

    The archer switches between melee and ranged attacks based on current target
    distance. This gives it a simple micro-management profile: it wants to keep
    enemies beyond ``RANGED_MIN_ATTACK_RANGE`` to use its stronger range.
    """

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 2.0
    DEFAULT_MAX_CARRY = 2
    DEFAULT_MAX_LIFE = 70
    DEFAULT_ATTACK_DAMAGE = 5
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 50
    DEFAULT_ATTACK_SPEED = 1
    MELEE_ATTACK_RANGE = 10
    RANGED_MIN_ATTACK_RANGE = 100
    RANGED_ATTACK_RANGE = 200
    DEFAULT_ATTACK_TYPE = (
        AttackType.MELEE,
        AttackType.RANGED,
    )
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_archer.png"))

    def _get_attack_distance(self, target: Entity) -> float:
        """Pick interaction distance based on archer dead-zone rules."""
        dist = distance_between(self, target)
        radius_sum = self.radius + getattr(target, "radius", 0)
        ranged_min = self.RANGED_MIN_ATTACK_RANGE + radius_sum
        if dist < ranged_min:
            return self.MELEE_ATTACK_RANGE + radius_sum
        range_bonus = calculate_height_range_bonus(
            self.height_level,
            getattr(target, "height_level", 0),
            AttackType.RANGED,
        )
        return self.RANGED_ATTACK_RANGE + range_bonus + radius_sum

    def _attack(self, target: Entity) -> None:
        """Choose melee or ranged attack mode before resolving damage."""
        dist = distance_between(self, target)
        radius_sum = self.radius + getattr(target, "radius", 0)
        ranged_min = self.RANGED_MIN_ATTACK_RANGE + radius_sum

        if dist < ranged_min:
            self.attack_type = AttackType.MELEE
            self.attack_range = self.MELEE_ATTACK_RANGE
        else:
            self.attack_type = AttackType.RANGED
            self.attack_range = self.RANGED_ATTACK_RANGE

        super()._attack(target)


class Mage(Unit):
    """Fragile long-range caster unit.

    Mages use ranged attacks only and emit ``MagicMissile`` VFX through the
    manager's attack-event pipeline.
    """

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 1.5
    DEFAULT_MAX_CARRY = 1
    DEFAULT_MAX_LIFE = 30
    DEFAULT_ATTACK_DAMAGE = 5
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 500
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.RANGED,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_mage.png"))
