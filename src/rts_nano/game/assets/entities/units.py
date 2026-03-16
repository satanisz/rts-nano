import math
from rts_nano.game.assets.entities.base_entities import Building
from rts_nano.game.assets.entities.base_entities import Resource
from pathlib import Path
from rts_nano.game.assets.entities.base_entities import Unit, TeamColor
from rts_nano.game.constants import *

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Peasant(Unit):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, UNIT_SIZE, UNIT_RADIUS)
        self.speed = UNIT_SPEED
        self.max_carry = UNIT_MAX_CARRY
        self.max_life = UNIT_LIFE
        self.life = UNIT_LIFE
        self.attack_damage = UNIT_ATTACK_DAMAGE
        self.attack_range = UNIT_ATTACK_RANGE
        self.attack_speed = UNIT_ATTACK_SPEED
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_peasant.png"))

    def harvest(self, entities):
        # Movement Logic
        if self.state == "MOVING":
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = math.sqrt(dx**2 + dy**2)

            interaction_dist = self.speed
            if self.target_entity:
                interaction_dist = self.radius + self.target_entity.radius + 2 # Touch boundaries + 2 px tolerance

            if dist < interaction_dist:
                # Snap to exact target only if we are moving to a point, not an entity
                if not self.target_entity:
                    self.x = self.target_x
                    self.y = self.target_y
                    
                if self.target_entity:
                    if isinstance(self.target_entity, Resource):
                        self.state = "GATHERING"
                    elif isinstance(self.target_entity, Building): # Base
                        self.state = "DEPOSITING"
                else:
                    self.state = "IDLE"
            else:
                self.x += (dx / dist) * self.speed
                self.y += (dy / dist) * self.speed
        
        # Collision Avoidance
        self.resolve_collisions(entities)

class Knight(Unit):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, KNIGHT_SIZE, KNIGHT_RADIUS)
        self.speed = KNIGHT_SPEED
        self.max_carry = KNIGHT_MAX_CARRY
        self.max_life = KNIGHT_LIFE
        self.life = KNIGHT_LIFE
        self.attack_damage = KNIGHT_ATTACK_DAMAGE
        self.attack_range = KNIGHT_ATTACK_RANGE
        self.attack_speed = KNIGHT_ATTACK_SPEED
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_knight.png"))

class Archer(Unit):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, ARCHER_SIZE, ARCHER_RADIUS)
        self.speed = ARCHER_SPEED
        self.max_carry = ARCHER_MAX_CARRY
        self.max_life = ARCHER_LIFE
        self.life = ARCHER_LIFE
        self.attack_damage = ARCHER_ATTACK_DAMAGE
        self.attack_range = ARCHER_ATTACK_RANGE
        self.attack_speed = ARCHER_ATTACK_SPEED
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_archer.png"))

class Mage(Unit):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team, MAGE_SIZE, MAGE_RADIUS)
        self.speed = MAGE_SPEED
        self.max_carry = MAGE_MAX_CARRY
        self.max_life = MAGE_LIFE
        self.life = MAGE_LIFE
        self.attack_damage = MAGE_ATTACK_DAMAGE
        self.attack_range = MAGE_ATTACK_RANGE
        self.attack_speed = MAGE_ATTACK_SPEED
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_mage.png"))
