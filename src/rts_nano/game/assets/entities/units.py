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
