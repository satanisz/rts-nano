"""Headless simulation helpers for tests and future RL integrations.

The playable game is pygame-based, but most simulation logic can advance
without opening a window. This module initializes pygame with SDL's dummy video
driver when needed, loads a map through the typed schema loader, and exposes a
small wrapper around ``GameManager``.

It is still pygame-aware because units use pygame time and input helpers
indirectly, but it does not create a display surface or draw frames.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from rts_nano.game.manager import GameManager
from rts_nano.map_schema import load_map_settings

if TYPE_CHECKING:
    from pathlib import Path

    from rts_nano.game.assets.entities.base_entities import TeamColor, Unit
    from rts_nano.map_schema import MapSettings


def initialize_headless_pygame() -> None:
    """Initialize pygame for simulation without opening a real window."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    if not pygame.get_init():
        pygame.init()


@dataclass
class HeadlessSimulation:
    """Small no-render wrapper around ``GameManager``.

    Args:
        manager: Game manager containing map state and simulation systems.

    The wrapper deliberately exposes ``manager`` for experiments that need full
    access, while common operations such as stepping frames and issuing orders
    get convenience methods.
    """

    manager: GameManager

    @classmethod
    def from_map_file(cls, path: Path) -> HeadlessSimulation:
        """Create a headless simulation from a map JSON file."""
        initialize_headless_pygame()
        return cls(GameManager(load_map_settings(path)))

    @classmethod
    def from_settings(cls, settings: MapSettings) -> HeadlessSimulation:
        """Create a headless simulation from already parsed map settings."""
        initialize_headless_pygame()
        return cls(GameManager(settings))

    def step(self, frames: int = 1) -> None:
        """Advance the simulation by a number of frames."""
        for _ in range(max(0, frames)):
            self.manager.update()

    def units_for_team(self, team: TeamColor) -> list[Unit]:
        """Return all living units for a team."""
        group = self.manager.entities.get(team)
        if group is None:
            return []
        return [*group.peasents, *group.knights, *group.archers, *group.mages]

    def issue_move_order(self, team: TeamColor, destination: tuple[float, float]) -> int:
        """Assign all units on a team a move order and return affected count."""
        units = self.units_for_team(team)
        self.manager._assign_group_move_order(units, (int(destination[0]), int(destination[1])))
        return len(units)

    def close(self) -> None:
        """Shut pygame down after a headless run."""
        if pygame.get_init():
            pygame.quit()
