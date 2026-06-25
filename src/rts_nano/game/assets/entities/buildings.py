"""Building entity implementations."""

from pathlib import Path

from rts_nano.game.assets.entities.base_entities import Building, TeamColor

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent


class Base(Building):
    """Represent the main team building used for resource drop-off.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "base"
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / f"{team.value.lower()}_base.png"),
            str(BASE_DIR / "assets" / "portraits" / "base.png"),
        )


class Barracks(Building):
    """Represent a basic military production building."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "barracks"


class House(Building):
    """Represent a support building that increases population capacity."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "house"


class MageTower(Building):
    """Represent an advanced production building that trains mages."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
        self.spec_key = "mage_tower"
