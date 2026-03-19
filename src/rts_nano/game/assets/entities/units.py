"""Unit entity implementations."""

import math
from pathlib import Path

from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, TeamColor, Unit
from rts_nano.game.constants import AttackType

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Peasant(Unit):
    """Worker unit that can gather and deposit resources."""

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
    """Ranged unit with moderate mobility."""

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
        tx, ty = target.get_center()
        dist = math.sqrt((tx - self.x) ** 2 + (ty - self.y) ** 2)
        radius_sum = self.radius + getattr(target, "radius", 0)
        ranged_min = self.RANGED_MIN_ATTACK_RANGE + radius_sum
        if dist < ranged_min:
            return self.MELEE_ATTACK_RANGE + radius_sum
        return self.RANGED_ATTACK_RANGE + radius_sum

    def _attack(self, target: Entity) -> None:
        """Use melee up to 20 range, otherwise use ranged in 30-50 range."""
        tx, ty = target.get_center()
        dist = math.sqrt((tx - self.x) ** 2 + (ty - self.y) ** 2)
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
    """Fragile ranged caster unit."""

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 1.5
    DEFAULT_MAX_CARRY = 1
    DEFAULT_MAX_LIFE = 30
    DEFA2LT_ATTACK_DAMAGE = 5
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 500
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.RANGED,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_mage.png"))
