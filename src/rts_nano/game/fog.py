from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rts_nano.game.constants import FOG_CELL_SIZE

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Entity


class FogOfWar:
    """Manages the map grid visibility state for the fog of war system.

    Grid states:
      0 = Unexplored (pure black)
      1 = Explored (dark overlay, cannot see enemy units)
      2 = Visible (fully visible, no overlay)
    """

    UNEXPLORED = 0
    EXPLORED = 1
    VISIBLE = 2

    def __init__(self, map_width: int, map_height: int) -> None:
        """Initialize the fog grid based on map size."""
        self.map_width = map_width
        self.map_height = map_height
        self.cols = int(math.ceil(map_width / FOG_CELL_SIZE))
        self.rows = int(math.ceil(map_height / FOG_CELL_SIZE))
        self.grid: list[list[int]] = [[self.UNEXPLORED for _ in range(self.cols)] for _ in range(self.rows)]
        self._visible_cells: set[tuple[int, int]] = set()

    def update(self, visible_entities: list[Entity] | None) -> None:
        """Recalculate visibility based on current team's units and structures.

        All previously visible cells are downgraded to explored.
        Then, new visible cells are calculated using entity vision ranges.
        """
        # Downgrade only the previously VISIBLE cells, avoiding a full-grid scan.
        for row, col in self._visible_cells:
            self.grid[row][col] = self.EXPLORED
        self._visible_cells.clear()

        if not visible_entities:
            return

        # Calculate new VISIBLE cells
        for entity in visible_entities:
            vision = getattr(entity, "vision_range", 0)
            if vision <= 0:
                continue

            cx, cy = entity.get_center()

            start_col = max(0, int((cx - vision) // FOG_CELL_SIZE))
            end_col = min(self.cols - 1, int((cx + vision) // FOG_CELL_SIZE))
            start_row = max(0, int((cy - vision) // FOG_CELL_SIZE))
            end_row = min(self.rows - 1, int((cy + vision) // FOG_CELL_SIZE))

            vision_sq = vision * vision

            for r in range(start_row, end_row + 1):
                cell_y = r * FOG_CELL_SIZE + FOG_CELL_SIZE / 2
                dy = cell_y - cy
                for c in range(start_col, end_col + 1):
                    cell_x = c * FOG_CELL_SIZE + FOG_CELL_SIZE / 2
                    dx = cell_x - cx
                    if dx * dx + dy * dy <= vision_sq:
                        self.grid[r][c] = self.VISIBLE
                        self._visible_cells.add((r, c))

    def is_visible(self, x: float, y: float) -> bool:
        """Return whether a world coordinate is currently visible."""
        col = int(x // FOG_CELL_SIZE)
        row = int(y // FOG_CELL_SIZE)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[row][col] == self.VISIBLE
        return False

    def is_explored(self, x: float, y: float) -> bool:
        """Return whether a world coordinate has been explored."""
        col = int(x // FOG_CELL_SIZE)
        row = int(y // FOG_CELL_SIZE)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[row][col] >= self.EXPLORED
        return False
