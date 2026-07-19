"""Uniform-grid spatial index for hot simulation proximity queries."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rts_nano.game.assets.entities.base_entities import Entity


class SpatialIndex:
    """Index entity centers in fixed-size cells for deterministic nearby lookup."""

    def __init__(self, cell_size: int = 128) -> None:
        """Create an empty index using cells of ``cell_size`` world units."""
        self.cell_size = max(1, cell_size)
        self.max_radius = 0.0
        self._cells: dict[tuple[int, int], list[Entity]] = {}

    def rebuild(self, entities: Iterable[Entity]) -> None:
        """Replace index contents with living entities from one simulation tick."""
        cells: defaultdict[tuple[int, int], list[Entity]] = defaultdict(list)
        max_radius = 0.0
        for entity in entities:
            if getattr(entity, "life", 1) <= 0:
                continue
            cells[self._cell(entity.x, entity.y)].append(entity)
            max_radius = max(max_radius, entity.radius)
        self._cells = dict(cells)
        self.max_radius = max_radius

    def query(self, center: tuple[float, float], radius: float) -> list[Entity]:
        """Return candidates whose center cells overlap a square query extent."""
        x, y = center
        extent = max(0.0, radius)
        min_col = math.floor((x - extent) / self.cell_size)
        max_col = math.floor((x + extent) / self.cell_size)
        min_row = math.floor((y - extent) / self.cell_size)
        max_row = math.floor((y + extent) / self.cell_size)
        return [
            entity
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
            for entity in self._cells.get((col, row), ())
        ]

    def _cell(self, x: float, y: float) -> tuple[int, int]:
        return math.floor(x / self.cell_size), math.floor(y / self.cell_size)
