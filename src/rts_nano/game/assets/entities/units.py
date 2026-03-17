"""Unit entity implementations."""

import math
from rts_nano.game.assets.entities.base_entities import Building
from rts_nano.game.assets.entities.base_entities import Resource
from pathlib import Path
from rts_nano.game.assets.entities.base_entities import Unit, TeamColor
from rts_nano.game.constants import AttackType

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Peasant(Unit):
    """Worker unit that can gather and deposit resources.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    SIZE = 30
    RADIUS = 10.0
    DEFAULT_SPEED = 2.0
    DEFAULT_MAX_CARRY = 10
    DEFAULT_MAX_LIFE = 5
    DEFAULT_ATTACK_DAMAGE = 3
    DEFAULT_ATTACK_RANGE = 0
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = AttackType.MELEE

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_peasant.png"))

    def harvest(self, entities):
        """Advance the peasant toward its target and resolve interactions.

        The unit enters gathering when it reaches a resource, depositing when
        it reaches a building, or returns to idle after point movement. It also
        performs basic collision avoidance against nearby entities.

        Args:
            entities: Entities used for collision resolution.
        """
        if self.state == "MOVING":
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = math.sqrt(dx**2 + dy**2)

            interaction_dist = self.speed
            if self.target_entity:
                interaction_dist = self.radius + self.target_entity.radius + 2

            if dist < interaction_dist:
                if not self.target_entity:
                    self.x = self.target_x
                    self.y = self.target_y

                if self.target_entity:
                    if isinstance(self.target_entity, Resource):
                        self.state = "GATHERING"
                    elif isinstance(self.target_entity, Building):
                        self.state = "DEPOSITING"
                else:
                    self.state = "IDLE"
            else:
                self.x += (dx / dist) * self.speed
                self.y += (dy / dist) * self.speed

        self.resolve_collisions(entities)

class Knight(Unit):
    """Frontline melee unit.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 2.5
    DEFAULT_MAX_CARRY = 3
    DEFAULT_MAX_LIFE = 100
    DEFAULT_ATTACK_DAMAGE = 10
    DEFAULT_ATTACK_RANGE = 50
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = AttackType.MELEE

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_knight.png"))

class Archer(Unit):
    """Ranged unit with moderate mobility.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 2.0
    DEFAULT_MAX_CARRY = 2
    DEFAULT_MAX_LIFE = 70
    DEFAULT_ATTACK_DAMAGE = 5
    DEFAULT_ATTACK_RANGE = 50
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = AttackType.RANGED

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_archer.png"))

class Mage(Unit):
    """Fragile ranged caster unit.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 1.5
    DEFAULT_MAX_CARRY = 1
    DEFAULT_MAX_LIFE = 30
    DEFAULT_ATTACK_DAMAGE = 5
    DEFAULT_ATTACK_RANGE = 50
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = AttackType.RANGED

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_mage.png"))
