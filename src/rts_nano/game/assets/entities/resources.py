"""Resource entity implementations."""

from pathlib import Path

from rts_nano.game.assets.entities.base_entities import Resource

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Cristal(Resource):
    """Represent a crystal resource node.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
    """

    def __init__(self, x: int, y: int) -> None:
        """Initialize the object."""
        super().__init__(x, y, "Cristal")
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / "cristal.png"), str(BASE_DIR / "assets" / "portraits" / "cristal.png")
        )


class Wood(Resource):
    """Represent a wood resource node.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
    """

    def __init__(self, x: int, y: int) -> None:
        """Initialize the object."""
        super().__init__(x, y, "Wood")
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / "wood.png"), str(BASE_DIR / "assets" / "portraits" / "wood.png")
        )
