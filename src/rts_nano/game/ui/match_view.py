"""Presentation-only visibility and inspection policy for players and spectators."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.application.match_controller import MatchMode
from rts_nano.game.fog import FogOfWar
from rts_nano.simulation.entities import TeamColor
from rts_nano.simulation.entities.base import Building, Entity, Resource, Unit

if TYPE_CHECKING:
    from rts_nano.application import GameSession


class MatchView:
    """Keep observer knowledge separate from game rules and each bot's memory."""

    def __init__(self, mode: MatchMode = MatchMode.PLAY) -> None:
        """Start a spectator in All view, or retain the normal player policy."""
        self.mode = mode
        self._perspective: TeamColor | None = None
        self._fogs: dict[TeamColor, FogOfWar] = {}

    @property
    def is_spectator(self) -> bool:
        """Return whether interaction is limited to observing the match."""
        return self.mode == MatchMode.SPECTATE

    @property
    def perspective(self) -> TeamColor | None:
        """Return the observer's team perspective, or None for All."""
        return self._perspective

    @property
    def label(self) -> str:
        """Return a concise observer perspective label."""
        return self._perspective.value if self._perspective is not None else "All"

    def reset(self) -> None:
        """Clear match-local exploration and restore the initial observer perspective."""
        self._perspective = None
        self._fogs.clear()

    def menu_options(self, manager: GameSession) -> list[str]:
        """Expose only working application controls to a spectator."""
        return [option for option in manager.menu_options if not self.is_spectator or option not in {"SAVE", "LOAD"}]

    def cycle_perspective(self, manager: GameSession) -> None:
        """Cycle All/Blue/Red without modifying any bot or simulation knowledge."""
        if not self.is_spectator:
            return
        views = (None, TeamColor.BLUE, TeamColor.RED)
        self._perspective = views[(views.index(self._perspective) + 1) % len(views)]
        manager.selected_entities.clear()
        manager.current_team = self._perspective or TeamColor.BLUE

    def refresh(self, manager: GameSession) -> None:
        """Refresh inspection knowledge; spectator grids never enter bot state."""
        if not self.is_spectator:
            manager.refresh_player_visibility()
            return
        for team in (TeamColor.BLUE, TeamColor.RED):
            fog = self._team_fog(manager, team)
            fog.update([entity for entity in manager.state.entities_for_team(team) if entity.life > 0])
        manager.selected_entities = [
            entity for entity in manager.selected_entities if self.can_inspect(manager, entity)
        ]

    def fog_for(self, manager: GameSession) -> FogOfWar | None:
        """Return the drawing grid; None denotes unobscured All view."""
        if not self.is_spectator:
            return manager.fog
        if self._perspective is None:
            return None
        return self._team_fog(manager, self._perspective)

    def _team_fog(self, manager: GameSession, team: TeamColor) -> FogOfWar:
        fog = self._fogs.get(team)
        if fog is None:
            fog = FogOfWar(manager.map_width, manager.map_height)
            self._fogs[team] = fog
        return fog

    def can_inspect(self, manager: GameSession, entity: Entity) -> bool:
        """Use the same visibility rule for drawing and spectator object selection."""
        if not self.is_spectator:
            return manager.can_player_target(entity)
        alive = entity.amount > 0 if isinstance(entity, Resource) else entity.life > 0
        if not alive:
            return False
        fog = self.fog_for(manager)
        if fog is None:
            return True
        if isinstance(entity, Resource):
            return fog.is_explored(*entity.get_center())
        return isinstance(entity, (Unit, Building)) and (
            entity.team == self._perspective or fog.is_visible(*entity.get_center())
        )

    def entity_at(self, manager: GameSession, position: tuple[float, float]) -> Entity | None:
        """Resolve read-only inspection without issuing player commands."""
        self.refresh(manager)
        point = (int(position[0]), int(position[1]))
        return next(
            (
                entity
                for entity in reversed(manager.all_entities)
                if entity.contains_point(point) and self.can_inspect(manager, entity)
            ),
            None,
        )
