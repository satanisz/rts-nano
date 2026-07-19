"""Uniform-grid spatial index for hot simulation proximity queries."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rts_nano.simulation.entities.base import Entity


class SpatialIndex:
    """Index entity centers in fixed-size cells for deterministic nearby lookup."""

    def __init__(self, cell_size: int = 128) -> None:
        """Create an empty index using cells of ``cell_size`` world units."""
        self.cell_size = max(1, cell_size)
        self.max_radius = 0.0
        self._cells: dict[tuple[int, int], list[Entity]] = {}
        self._entity_cells: dict[Entity, tuple[int, int]] = {}

    def rebuild(self, entities: Iterable[Entity]) -> None:
        """Replace index contents with living entities from one simulation tick."""
        cells: defaultdict[tuple[int, int], list[Entity]] = defaultdict(list)
        max_radius = 0.0
        entity_cells: dict[Entity, tuple[int, int]] = {}
        for entity in entities:
            if getattr(entity, "life", 1) <= 0:
                continue
            cell = self._cell(entity.x, entity.y)
            cells[cell].append(entity)
            entity_cells[entity] = cell
            max_radius = max(max_radius, entity.radius)
        self._cells = dict(cells)
        self._entity_cells = entity_cells
        self.max_radius = max_radius

    def add(self, entity: Entity) -> None:
        """Add one living entity without rebuilding unrelated cells."""
        if getattr(entity, "life", 1) <= 0:
            return
        cell = self._cell(entity.x, entity.y)
        self._cells.setdefault(cell, []).append(entity)
        self._entity_cells[entity] = cell
        self.max_radius = max(self.max_radius, entity.radius)

    def update(self, entity: Entity) -> None:
        """Move one entity between cells after its simulation update."""
        if getattr(entity, "life", 1) <= 0:
            self.remove(entity)
            return
        old_cell = self._entity_cells.get(entity)
        new_cell = self._cell(entity.x, entity.y)
        if old_cell == new_cell:
            return
        if old_cell is not None:
            old_entities = self._cells[old_cell]
            old_entities.remove(entity)
            if not old_entities:
                del self._cells[old_cell]
        self._cells.setdefault(new_cell, []).append(entity)
        self._entity_cells[entity] = new_cell
        self.max_radius = max(self.max_radius, entity.radius)

    def remove(self, entity: Entity) -> None:
        """Remove one entity without rebuilding unrelated cells."""
        cell = self._entity_cells.pop(entity, None)
        if cell is None:
            return
        entities = self._cells[cell]
        entities.remove(entity)
        if not entities:
            del self._cells[cell]
        if entity.radius >= self.max_radius:
            self.max_radius = max(
                (remaining.radius for cell_entities in self._cells.values() for remaining in cell_entities),
                default=0.0,
            )

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
