"""Headless simulation helpers for tests and future RL integrations.

Simulation logic advances without importing Pygame, configuring SDL, or opening
a window. This module loads a map through the typed schema loader and exposes a
small wrapper around ``GameSession``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rts_nano.application import GameSession
from rts_nano.map_schema import load_map_settings

if TYPE_CHECKING:
    from pathlib import Path

    from rts_nano.map_schema import MapSettings
    from rts_nano.simulation.entities.base import TeamColor, Unit


@dataclass
class HeadlessSimulation:
    """Small no-render wrapper around ``GameSession``.

    Args:
        manager: Game manager containing map state and simulation systems.

    The wrapper deliberately exposes ``manager`` for experiments that need full
    access, while common operations such as stepping frames and issuing orders
    get convenience methods.
    """

    manager: GameSession

    @classmethod
    def from_map_file(cls, path: Path) -> HeadlessSimulation:
        """Create a headless simulation from a map JSON file."""
        return cls(GameSession(load_map_settings(path)))

    @classmethod
    def from_settings(cls, settings: MapSettings) -> HeadlessSimulation:
        """Create a headless simulation from already parsed map settings."""
        return cls(GameSession(settings))

    def step(self, frames: int = 1) -> None:
        """Advance the simulation by a number of frames."""
        for _ in range(max(0, frames)):
            self.manager.update()

    def units_for_team(self, team: TeamColor) -> list[Unit]:
        """Return all living units for a team."""
        return self.manager.units_for_team(team)

    def issue_move_order(self, team: TeamColor, destination: tuple[float, float]) -> int:
        """Assign all units on a team a move order and return affected count."""
        return self.manager.issue_move_order(team, destination)

    def close(self) -> None:
        """Release simulation-owned resources (currently none)."""
