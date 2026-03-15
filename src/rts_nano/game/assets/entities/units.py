import math
from rts_nano.game.assets.entities.base_entities import Building
from rts_nano.game.assets.entities.base_entities import Resource
from pathlib import Path
from rts_nano.game.assets.entities.base_entities import Unit, TeamColor
from rts_nano.game.constants import *

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Peasant(Unit):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team)
        self.speed = UNIT_SPEED
        self.max_carry = UNIT_MAX_CARRY
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_peasant.png"))

    def harvest(self, entities):
        # Movement Logic
        if self.state == "MOVING":
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = math.sqrt(dx**2 + dy**2)

            # Determine interaction distance
            interaction_dist = self.speed
            if self.target_entity:
                interaction_dist = self.radius + self.target_entity.radius + 5 # 5 pixel tolerance

            if dist < interaction_dist:
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
        super().__init__(x, y, team)
        self.speed = KNIGHT_SPEED
        self.max_carry = KNIGHT_MAX_CARRY
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_knight.png"))

class Archer(Unit):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team)
        self.speed = ARCHER_SPEED
        self.max_carry = ARCHER_MAX_CARRY
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_archer.png"))

class Mage(Unit):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team)
        self.speed = MAGE_SPEED
        self.max_carry = MAGE_MAX_CARRY
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_mage.png"))
