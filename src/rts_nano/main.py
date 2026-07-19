"""Application entry point for the playable RTS Nano game.

This module intentionally stays thin. It owns pygame display creation,
fullscreen/window fallback behavior, and the outer event/update/draw loop. The
actual game state lives in :class:`rts_nano.game.manager.GameSession`; keep new
gameplay logic there unless it truly concerns process startup, display mode, or
top-level event dispatch.

Rendering uses the real pygame display size. In windowed mode the initial
window follows the monitor aspect ratio; in fullscreen mode pygame is asked for
native fullscreen first. The manager is told the current display size each frame
so camera limits, minimap, HUD, and edge scrolling can adapt without bitmap
stretching.
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

import pygame

from rts_nano.ai import ScriptedAI
from rts_nano.application import GameSession
from rts_nano.game.constants import FPS, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH
from rts_nano.game.ui.input_controller import FULLSCREEN_TOGGLE_EVENT, InputController
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.game.ui.state import PresentationState
from rts_nano.map_schema import load_map_settings
from rts_nano.simulation.entities import TeamColor

BASE_DIR = Path(__file__).resolve().parent
MAPS_DIR = BASE_DIR / "maps"
DEFAULT_GAME_MAP = Path("map_spec_01.json")
WINDOWED_BASE_HEIGHT = SCREEN_HEIGHT


def _resolve_game_map_path(path: Path) -> Path:
    """Resolve a CLI map name against the packaged maps directory."""
    if path.exists() or path.is_absolute():
        return path
    candidate = path if path.suffix == ".json" else path.with_suffix(".json")
    return MAPS_DIR / candidate.name


def _parse_args() -> Path:
    """Return the requested playable map path."""
    parser = ArgumentParser(description="Play RTS Nano")
    parser.add_argument("--map", type=Path, default=DEFAULT_GAME_MAP, help="Map JSON path or packaged map name")
    return _resolve_game_map_path(parser.parse_args().map)


def _desktop_size() -> tuple[int, int]:
    """Return the current desktop size, falling back to the original game size.

    Pygame can report zeroes on some drivers before the video system is fully
    settled. The fallback keeps display creation deterministic for tests and
    unusual SDL backends.
    """
    info = pygame.display.Info()
    width = info.current_w or SCREEN_WIDTH
    height = info.current_h or SCREEN_HEIGHT
    return width, height


def _windowed_size() -> tuple[int, int]:
    """Pick an initial window size that follows the monitor aspect ratio.

    The game no longer renders to a fixed off-screen buffer and stretches it.
    Instead the window itself changes shape and the game draws directly into
    that surface. This helper keeps windowed mode visually close to fullscreen
    proportions while leaving a small margin for the operating-system desktop.
    """
    desktop_width, desktop_height = _desktop_size()
    if desktop_width <= 0 or desktop_height <= 0:
        return SCREEN_WIDTH, SCREEN_HEIGHT

    height = min(WINDOWED_BASE_HEIGHT, max(360, desktop_height - 80))
    width = int(height * desktop_width / desktop_height)
    if width > desktop_width - 80:
        width = max(640, desktop_width - 80)
        height = int(width * desktop_height / desktop_width)
    return max(640, width), max(360, height)


def _create_display(*, fullscreen: bool) -> tuple[pygame.Surface, bool]:
    """Create the game display surface and report whether fullscreen succeeded.

    Fullscreen is attempted in descending order of desirability:

    1. ``(0, 0), pygame.FULLSCREEN`` lets SDL pick the native monitor mode and
       is most likely to hide the Windows taskbar.
    2. The explicit desktop size is a useful fallback for drivers that reject
       ``(0, 0)``.
    3. The original project size keeps the game usable if native fullscreen is
       unavailable.

    Returning the actual fullscreen state lets the F10 menu stay synchronized
    even when SDL falls back to windowed mode.
    """
    if not fullscreen:
        return pygame.display.set_mode(_windowed_size()), False

    fullscreen_attempts = (
        lambda: ((0, 0), pygame.FULLSCREEN),
        lambda: (_desktop_size(), pygame.FULLSCREEN),
        lambda: ((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN),
    )
    for get_attempt in fullscreen_attempts:
        size, flags = get_attempt()
        try:
            return pygame.display.set_mode(size, flags), True
        except pygame.error:
            continue

    return pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT)), False


def main() -> None:
    """Run the pygame loop for the default map.

    The loop order is:

    1. Refresh manager viewport/mouse state from the current display surface.
    2. Forward pygame events to the manager, handling only process-level events
       such as quit and fullscreen toggles locally.
    3. Advance simulation.
    4. Draw the world and UI directly onto the display surface.

    Keeping the display surface as the render target is important: it means
    fullscreen shows more map instead of stretching a fixed-resolution image.
    """
    map_path = _parse_args()
    pygame.init()
    display_screen, _ = _create_display(fullscreen=False)
    pygame.display.set_caption("Simple RTS")
    clock = pygame.time.Clock()

    map_settings = load_map_settings(map_path)
    game_manager = GameSession(map_settings)
    game_manager.set_viewport_size(*display_screen.get_size())
    presentation = PresentationState()
    renderer = GameRenderer(presentation=presentation)
    input_controller = InputController(presentation=presentation)
    opponent_ai = ScriptedAI(game_manager, TeamColor.RED)

    running = True
    while running:
        display_size = display_screen.get_size()
        game_manager.set_viewport_size(*display_size)
        game_manager.set_mouse_pos(pygame.mouse.get_pos())

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == FULLSCREEN_TOGGLE_EVENT:
                display_screen, fullscreen_enabled = _create_display(fullscreen=event.enabled)
                game_manager.set_fullscreen_enabled(fullscreen_enabled)
                game_manager.set_viewport_size(*display_screen.get_size())
            input_controller.handle_event(game_manager, event)

        input_controller.update_camera(game_manager)
        if not game_manager.paused:
            opponent_ai.step()
        game_manager.update()

        display_screen.fill(GRAY)
        renderer.draw(display_screen, game_manager)

        pygame.display.flip()
        clock.tick(FPS * game_manager.fps_multiplier)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
