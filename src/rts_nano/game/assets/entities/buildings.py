"""Building entity implementations."""

from pathlib import Path
from rts_nano.game.assets.entities.base_entities import Building, TeamColor
from rts_nano.game.constants import *

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

class Base(Building):
    """Represent the main team building used for resource drop-off.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        super().__init__(x, y, team)
        self.load_image(str(BASE_DIR / "assets" / f"{team.value.lower()}_base.png"))
