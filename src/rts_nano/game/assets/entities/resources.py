"""Resource entity implementations."""

from pathlib import Path

from rts_nano.game.assets.entities.base_entities import Resource
from rts_nano.game.constants import *

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Cristal(Resource):
    """Represent a crystal resource node.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
    """

    def __init__(self, x: int, y: int) -> None:
        super().__init__(x, y, "Cristal")
        self.load_image(str(BASE_DIR / "assets" / "cristal.png"))


class Wood(Resource):
    """Represent a wood resource node.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
    """

    def __init__(self, x: int, y: int) -> None:
        super().__init__(x, y, "Wood")
        self.load_image(str(BASE_DIR / "assets" / "wood.png"))
