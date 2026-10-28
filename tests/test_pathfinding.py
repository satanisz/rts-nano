"""Tests for grid-based pathfinding."""

from __future__ import annotations

from rts_nano.game.pathfinding import find_path


def test_find_path_returns_goal_when_cells_match() -> None:
    """A same-cell goal returns the exact requested goal point."""
    path = find_path((5, 5), (8, 8), width=100, height=100, can_move_between=lambda _a, _b: True, grid_size=16)

    assert path == [(8, 8)]


def test_find_path_routes_through_gap() -> None:
    """A* can route around blocked cells and still end at the exact goal."""
    blocked = {(2, 0), (2, 1), (2, 3), (2, 4)}

    def can_move_between(_current: tuple[float, float], next_point: tuple[float, float]) -> bool:
        cell = int(next_point[0] // 10), int(next_point[1] // 10)
        return cell not in blocked

    path = find_path((5, 5), (45, 45), width=50, height=50, can_move_between=can_move_between, grid_size=10)

    assert path
    assert path[-1] == (45, 45)
    assert all((int(x // 10), int(y // 10)) not in blocked for x, y in path)


def test_path_checks_actual_start_and_goal_connections() -> None:
    """A coarse cell center must not stand in for either exact endpoint."""
    start = (2, 8)
    goal = (38, 2)

    def can_move_between(current: tuple[float, float], next_point: tuple[float, float]) -> bool:
        if current == start:
            return next_point == (5, 15)
        if next_point == goal:
            return current == (35, 15)
        return True

    path = find_path(start, goal, width=50, height=40, can_move_between=can_move_between, grid_size=10)

    assert path[0] == (5, 15)
    assert path[-2:] == [(35, 15), goal]
    assert all(can_move_between(a, b) for a, b in zip([start, *path[:-1]], path, strict=True))


def test_same_cell_does_not_allow_a_blocked_direct_connection() -> None:
    assert not find_path((2, 2), (8, 8), width=20, height=20, can_move_between=lambda _a, _b: False, grid_size=10)
