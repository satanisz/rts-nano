"""Headless simulation helpers for tests and future RL integrations.

The playable game is pygame-based, but simulation logic can advance without
initializing SDL subsystems or opening a window. This module configures the
dummy video driver defensively, loads a map through the typed schema loader,
and exposes a small wrapper around ``GameManager``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rts_nano.game.manager import GameManager
from rts_nano.map_schema import load_map_settings

if TYPE_CHECKING:
    from pathlib import Path

    from rts_nano.game.assets.entities.base_entities import TeamColor, Unit
    from rts_nano.map_schema import MapSettings


def initialize_headless_pygame() -> None:
    """Configure SDL defensively without initializing unused subsystems."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


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
        return cls(GameManager(load_map_settings(path), load_visuals=False))

    @classmethod
    def from_settings(cls, settings: MapSettings) -> HeadlessSimulation:
        """Create a headless simulation from already parsed map settings."""
        initialize_headless_pygame()
        return cls(GameManager(settings, load_visuals=False))

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
