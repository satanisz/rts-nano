"""Victory detection over the shared ``GameState``.

A team stays active while it owns at least one living entity. When only one team
remains it wins; when none remain the match is a draw. The result is written to
``GameState`` (``game_over_message`` and ``paused``) so observation, HUD, and env
terminal checks keep reading the same fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.game.state import GameState


class VictorySystem:
    """Resolve simple elimination victory over a game state."""

    def __init__(self, state: GameState) -> None:
        """Initialize the victory system for one game state."""
        self._state = state

    def update(self) -> None:
        """Detect a terminal win/draw and record it on the game state."""
        active_teams = [
            team
            for team, group in self._state.entities.items()
            if team != TeamColor.RESOURCES and any(entity.life > 0 for entity in group.all_entities)
        ]
        if len(active_teams) == 1:
            self._state.game_over_message = f"Team {active_teams[0].value} wins"
            self._state.paused = True
        elif not active_teams:
            self._state.game_over_message = "Draw"
            self._state.paused = True
