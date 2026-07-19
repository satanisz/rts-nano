"""Resource entity implementations."""

from rts_nano.content import CONTENT
from rts_nano.simulation.entities.base import Resource


class Gold(Resource):
    """Represent a gold resource node.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
    """

    def __init__(self, x: int, y: int) -> None:
        """Initialize the object."""
        super().__init__(x, y, CONTENT.get_resource("gold"))


class Wood(Resource):
    """Represent a wood resource node.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
    """

    def __init__(self, x: int, y: int) -> None:
        """Initialize the object."""
        super().__init__(x, y, CONTENT.get_resource("wood"))
