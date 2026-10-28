"""Application-owned match participants and lifecycle, independent of presentation."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from rts_nano.ai import ScriptedAI
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from .game_session import GameSession


class MatchMode(StrEnum):
    """Supported interactive participant configurations."""

    PLAY = "play"
    SPECTATE = "spectate"


class MatchController:
    """Own participants and advance their decisions before the shared game tick."""

    def __init__(self, session: GameSession, mode: MatchMode = MatchMode.PLAY) -> None:
        """Compose fresh baseline bots for the requested match mode."""
        self.session = session
        self.mode = mode
        teams = (TeamColor.BLUE, TeamColor.RED) if mode == MatchMode.SPECTATE else (TeamColor.RED,)
        self._bots = tuple(ScriptedAI(session, team) for team in teams)

    def step(self) -> None:
        """Advance both participant decisions and simulation, respecting pause/result."""
        if self.session.paused or self.session.game_over_message is not None:
            return
        for bot in self._bots:
            bot.step()
        self.session.update()

    def restart(self) -> MatchController:
        """Create a fresh match with the same mode and the session's restart rules."""
        return type(self)(self.session.restart(), self.mode)
