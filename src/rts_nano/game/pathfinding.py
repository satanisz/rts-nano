"""Grid-based A* pathfinding helpers for terrain-aware movement.

The pathfinder operates on world coordinates but searches a coarse square grid.
It is intentionally independent of pygame terrain classes: callers provide a
``can_move_between(current, next_point)`` predicate, which lets ``GameManager``
inject water, rock, and ramp/height rules from ``TerrainMap``.

Returned paths are waypoint lists in world coordinates. An empty list means no
path was found within ``MAX_EXPLORED_CELLS``; units can still attempt local
direct movement if the manager chooses to assign the target.
"""

from __future__ import annotations

import heapq
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

Point = tuple[float, float]
Cell = tuple[int, int]

GRID_SIZE = 32
MAX_EXPLORED_CELLS = 12000
ORTHOGONAL_COST = 10
DIAGONAL_COST = 14


def find_path(
    start: Point,
    goal: Point,
    *,
    width: int,
    height: int,
    can_move_between: Callable[[Point, Point], bool],
    grid_size: int = GRID_SIZE,
) -> list[Point]:
    """Find terrain-aware waypoints from start to goal using A*.

    Args:
        start: Unit center in world coordinates.
        goal: Desired destination in world coordinates.
        width: Searchable map width.
        height: Searchable map height.
        can_move_between: Terrain/collision predicate for adjacent grid-cell
            centers.
        grid_size: Size of one search cell in world pixels.

    The search uses 8-neighbor movement and octile distance. Diagonal moves are
    additionally checked through their horizontal and vertical components to
    avoid clipping around blocked corners.
    """
    start_cell = _point_to_cell(start, grid_size)
    goal_cell = _point_to_cell(goal, grid_size)
    max_col = max(0, (width - 1) // grid_size)
    max_row = max(0, (height - 1) // grid_size)

    start_cell = _clamp_cell(start_cell, max_col, max_row)
    goal_cell = _clamp_cell(goal_cell, max_col, max_row)

    if start_cell == goal_cell:
        return [goal]

    frontier: list[tuple[int, int, Cell]] = []
    heapq.heappush(frontier, (0, 0, start_cell))
    came_from: dict[Cell, Cell | None] = {start_cell: None}
    cost_so_far: dict[Cell, int] = {start_cell: 0}
    explored = 0

    while frontier and explored < MAX_EXPLORED_CELLS:
        _, _, current = heapq.heappop(frontier)
        explored += 1

        if current == goal_cell:
            return _reconstruct_path(came_from, current, goal, grid_size, width, height)

        current_point = _cell_center(current, grid_size, width, height)
        for neighbor, move_cost in _neighbors(current, max_col, max_row):
            neighbor_point = _cell_center(neighbor, grid_size, width, height)
            if not can_move_between(current_point, neighbor_point):
                continue

            if _is_diagonal(current, neighbor) and not _allows_diagonal_step(
                current,
                neighbor,
                width=width,
                height=height,
                grid_size=grid_size,
                can_move_between=can_move_between,
            ):
                continue

            new_cost = cost_so_far[current] + move_cost
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + _heuristic(neighbor, goal_cell)
                heapq.heappush(frontier, (priority, explored, neighbor))
                came_from[neighbor] = current

    return []


def _point_to_cell(point: Point, grid_size: int) -> Cell:
    """Convert a world point to a grid cell."""
    return int(point[0] // grid_size), int(point[1] // grid_size)


def _clamp_cell(cell: Cell, max_col: int, max_row: int) -> Cell:
    """Clamp a cell to grid bounds."""
    col, row = cell
    return min(max(col, 0), max_col), min(max(row, 0), max_row)


def _cell_center(cell: Cell, grid_size: int, width: int, height: int) -> Point:
    """Return the center point of a grid cell."""
    col, row = cell
    x = min(col * grid_size + grid_size / 2, width - 1)
    y = min(row * grid_size + grid_size / 2, height - 1)
    return x, y


def _neighbors(cell: Cell, max_col: int, max_row: int) -> list[tuple[Cell, int]]:
    """Return adjacent cells with movement costs."""
    col, row = cell
    candidates = [
        ((col - 1, row), ORTHOGONAL_COST),
        ((col + 1, row), ORTHOGONAL_COST),
        ((col, row - 1), ORTHOGONAL_COST),
        ((col, row + 1), ORTHOGONAL_COST),
        ((col - 1, row - 1), DIAGONAL_COST),
        ((col + 1, row - 1), DIAGONAL_COST),
        ((col - 1, row + 1), DIAGONAL_COST),
        ((col + 1, row + 1), DIAGONAL_COST),
    ]
    return [
        (candidate, cost)
        for candidate, cost in candidates
        if 0 <= candidate[0] <= max_col and 0 <= candidate[1] <= max_row
    ]


def _is_diagonal(current: Cell, neighbor: Cell) -> bool:
    """Return whether a neighbor step is diagonal."""
    return current[0] != neighbor[0] and current[1] != neighbor[1]


def _allows_diagonal_step(
    current: Cell,
    neighbor: Cell,
    *,
    width: int,
    height: int,
    grid_size: int,
    can_move_between: Callable[[Point, Point], bool],
) -> bool:
    """Prevent diagonal clipping through blocked corners.

    A diagonal step is accepted only if the corresponding horizontal and
    vertical axis-aligned steps are both valid. This matters for water/rock
    corners and ramp boundaries, where a purely diagonal edge could otherwise
    sneak through terrain that no unit should cross.
    """
    horizontal = (neighbor[0], current[1])
    vertical = (current[0], neighbor[1])
    current_point = _cell_center(current, grid_size, width, height)
    horizontal_point = _cell_center(horizontal, grid_size, width, height)
    vertical_point = _cell_center(vertical, grid_size, width, height)
    return can_move_between(current_point, horizontal_point) and can_move_between(current_point, vertical_point)


def _heuristic(cell: Cell, goal: Cell) -> int:
    """Octile distance heuristic for an 8-neighbor grid."""
    dx = abs(cell[0] - goal[0])
    dy = abs(cell[1] - goal[1])
    return ORTHOGONAL_COST * (dx + dy) + (DIAGONAL_COST - 2 * ORTHOGONAL_COST) * min(dx, dy)


def _reconstruct_path(
    came_from: dict[Cell, Cell | None],
    current: Cell,
    goal: Point,
    grid_size: int,
    width: int,
    height: int,
) -> list[Point]:
    """Build waypoints from a completed A* search."""
    cells = [current]
    while True:
        previous = came_from[current]
        if previous is None:
            break
        current = previous
        cells.append(current)
    cells.reverse()

    waypoints = [_cell_center(cell, grid_size, width, height) for cell in cells[1:]]
    if waypoints:
        waypoints[-1] = goal
    else:
        waypoints.append(goal)
    return waypoints
