"""Game-wide constants used for rendering, simulation, and balancing.

This module holds defaults, not necessarily live viewport state. The playable
game can resize its viewport at runtime through ``GameManager.set_viewport_size``
because fullscreen/windowed mode renders directly to the current display
surface. New code that needs the current screen dimensions during gameplay
should generally ask the manager or use manager helpers instead of importing
``SCREEN_WIDTH``/``SCREEN_HEIGHT`` once and assuming they never change.

Balance constants here are intentionally small and visible. Unit-specific
balance lives on concrete unit classes.

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
    NONE = "None"


SCREEN_WIDTH: int = 1600
SCREEN_HEIGHT: int = 720
BOTTOM_MENU_HEIGHT: int = 174

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
CYAN = (0, 255, 255)
GRAY = (128, 128, 128)

FPS: float = 60.0
HARVEST_SEARCH_RADIUS: float = 300.0
MAX_UNITS: int = 50
