"""Unit entity implementations."""

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
    DEFAULT_ATTACK_RANGE = 50
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.MELEE,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
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
    DEFAULT_ATTACK_TYPE = (AttackType.MELEE, AttackType.RANGED,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_archer.png"))

class Mage(Unit):
    """Fragile ranged caster unit."""

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
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_mage.png"))
