"""Layout and English labels for the terminal match overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from rts_nano.game.constants import FPS

if TYPE_CHECKING:
    from rts_nano.application import GameSession

RESULT_BUTTON_WIDTH = 240
RESULT_BUTTON_HEIGHT = 52
RESULT_BUTTON_GAP = 16


def match_clock_label(manager: GameSession) -> str:
    """Format simulation time and the optional match limit for the HUD."""

    def clock(frames: int) -> str:
        seconds = int(frames / FPS)
        return f"{seconds // 60}:{seconds % 60:02d}"

    label = f"Time {clock(manager.state.tick_count)}"
    if manager.state.match_rules.max_frames is not None:
        label += f" / {clock(manager.state.match_rules.max_frames)}"
    return label


def match_result_detail(manager: GameSession) -> str:
    """Explain the terminal gameplay rule independently of player perspective."""
    if manager.state.match_end_reason == "time_limit":
        return "Time limit reached."
    if manager.game_over_message == "Draw":
        return "Both teams eliminated."
    return "All opposing forces eliminated."


def match_result_title(manager: GameSession) -> str:
    """Return the result from the current player's perspective."""
    message = manager.game_over_message
    if message == "Draw":
        return "DRAW"
    if message == f"Team {manager.current_team.value} wins":
        return "VICTORY"
    return "DEFEAT"


def match_result_buttons(screen_width: int, screen_height: int) -> tuple[tuple[str, pygame.Rect], ...]:
    """Return shared renderer/input hitboxes for terminal actions."""
    left = (screen_width - RESULT_BUTTON_WIDTH) // 2
    top = screen_height // 2 + 34
    return (
        ("RESTART MATCH", pygame.Rect(left, top, RESULT_BUTTON_WIDTH, RESULT_BUTTON_HEIGHT)),
        (
            "QUIT GAME",
            pygame.Rect(
                left,
                top + RESULT_BUTTON_HEIGHT + RESULT_BUTTON_GAP,
                RESULT_BUTTON_WIDTH,
                RESULT_BUTTON_HEIGHT,
            ),
        ),
    )
