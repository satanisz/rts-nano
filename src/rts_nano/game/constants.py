"""Game-wide constants used for rendering, simulation, and balancing.

Attributes:
    AttackType: String enum for supported attack categories.
    SCREEN_WIDTH: Width of the game window in pixels.
    SCREEN_HEIGHT: Height of the game window in pixels.
    BOTTOM_MENU_HEIGHT: Height of the lower UI panel in pixels.
    WHITE: RGB tuple for white.
    BLACK: RGB tuple for black.
    RED: RGB tuple for red.
    GREEN: RGB tuple for green.
    BLUE: RGB tuple for blue.
    YELLOW: RGB tuple for yellow.
    CYAN: RGB tuple for cyan.
    GRAY: RGB tuple for gray.
    FPS: Target frames per second.
    HARVEST_SEARCH_RADIUS: Maximum radius for searching replacement resources.
"""

from enum import StrEnum


class AttackType(StrEnum):
    """Supported attack categories for units."""

    MELEE = "Melee"
    RANGED = "Ranged"


SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 720
BOTTOM_MENU_HEIGHT = 120

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
GRAY = (128, 128, 128)

FPS: int = 60
HARVEST_SEARCH_RADIUS: float = 300.0
