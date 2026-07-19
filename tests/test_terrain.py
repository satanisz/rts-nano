"""Tests for terrain loading and movement semantics."""

from __future__ import annotations

import pygame

from rts_nano.game.terrain import TerrainMap
from rts_nano.game.ui.terrain_renderer import TerrainRenderer


def test_grouped_high_ground_loads_as_shapes_and_flat_regions() -> None:
    """Grouped terrain is preserved for rendering and flattened for queries."""
    terrain = TerrainMap(
        {
            "high_ground": [[[10, 10, 40, 40], [50, 10, 40, 40]]],
            "water": [[[100, 100, 30, 30]]],
        }
    )

    assert len(terrain.high_ground_shapes) == 1
    assert len(terrain.high_ground) == 2
    assert terrain.height_at((20, 20)) == 1
    assert terrain.height_at((70, 20)) == 1
    assert terrain.height_at((5, 5)) == 0
    assert terrain.blocks_movement((110, 110))


def test_height_transition_requires_ramp() -> None:
    """Units can move between low and high ground only via ramps."""
    terrain = TerrainMap(
        {
            "high_ground": [[[50, 50, 100, 100]]],
            "ramps": [[40, 80, 20, 30]],
        }
    )

    assert not terrain.allows_height_transition((20, 20), (80, 80))
    assert terrain.allows_height_transition((45, 90), (80, 90))


def test_grouped_terrain_draws_without_crashing() -> None:
    """The grouped renderer handles non-rectangular joined shapes."""
    screen = pygame.Surface((240, 180))
    terrain = TerrainMap(
        {
            "high_ground": [[[10, 10, 80, 60], [60, 60, 100, 60]]],
            "water": [[[20, 130, 60, 30], [80, 120, 50, 40]]],
        }
    )

    TerrainRenderer().draw(screen, terrain, (0, 0))
