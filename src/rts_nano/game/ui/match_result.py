"""Layout and English labels for the terminal match overlay."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from rts_nano.application import GameSession

RESULT_BUTTON_WIDTH = 240
RESULT_BUTTON_HEIGHT = 52
RESULT_BUTTON_GAP = 16


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
