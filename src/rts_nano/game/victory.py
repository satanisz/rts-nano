"""Victory detection extracted from ``GameManager``.

A team stays active while it owns at least one living entity. When only one team
remains it wins; when none remain the match is a draw. The system writes the
result back onto the manager (``game_over_message`` and ``paused``) so existing
observation, HUD, and env terminal checks keep reading the same fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.game.manager import GameManager


class VictorySystem:
    """Resolve simple elimination victory for one manager."""

    def __init__(self, manager: GameManager) -> None:
        """Initialize the victory system for one game manager."""
        self._manager = manager

    def update(self) -> None:
        """Detect a terminal win/draw and record it on the manager."""
        active_teams = [
            team
            for team, group in self._manager.entities.items()
            if team != TeamColor.RESOURCES and any(entity.life > 0 for entity in group.all_entities)
        ]
        if len(active_teams) == 1:
            self._manager.game_over_message = f"Team {active_teams[0].value} wins"
            self._manager.paused = True
        elif not active_teams:
            self._manager.game_over_message = "Draw"
            self._manager.paused = True
