from pathlib import Path
from rts_nano.game.assets.entities.base_entities import Building, TeamColor
from rts_nano.game.constants import *

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Base(Building):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        super().__init__(x, y, team)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_base.png"))
