"""Victory detection over the shared ``GameState``.

A team stays active while it owns at least one living entity. When only one team
remains it wins; when none remain the match is a draw. The result is written to
``GameState`` (``game_over_message``) so observation, HUD, and env
terminal checks keep reading the same fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
            team for team in self._state.teams if any(entity.life > 0 for entity in self._state.entities_for_team(team))
        ]
        if len(active_teams) == 1:
            self._state.game_over_message = f"Team {active_teams[0].value} wins"
        elif not active_teams:
            self._state.game_over_message = "Draw"
