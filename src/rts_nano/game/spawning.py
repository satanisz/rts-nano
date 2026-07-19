"""Deterministic placement of completed units around production buildings."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rts_nano.simulation.entities.base import Building, Unit

MAX_SPAWN_SEARCH_RADIUS = 128

if TYPE_CHECKING:
    from rts_nano.content import UnitDefinition
    from rts_nano.game.state import GameState


def find_spawn_point(
    state: GameState,
    producer: Building,
    definition: UnitDefinition,
) -> tuple[int, int] | None:
    """Return the nearest valid deterministic lattice point, or ``None``.

    A completed job remains queued when this search fails and is retried on a
    later tick. This prevents paid units from being lost on crowded maps.
    """
    clearance = producer.radius + definition.radius + 2
    step = max(8, math.ceil(definition.radius * 2 + 2))
    max_ring = math.ceil(MAX_SPAWN_SEARCH_RADIUS / step)
    candidates: list[tuple[float, int, int]] = []

    # Include exact cardinal exits before the regular lattice so compact maps
    # do not depend on the unit-size grid lining up with a producer edge.
    for x, y in (
        (producer.x, producer.y - clearance),
        (producer.x - clearance, producer.y),
        (producer.x + clearance, producer.y),
        (producer.x, producer.y + clearance),
    ):
        candidates.append(((x - producer.x) ** 2 + (y - producer.y) ** 2, round(y), round(x)))

    for ring in range(1, max_ring + 1):
        for grid_y in range(-ring, ring + 1):
            for grid_x in range(-ring, ring + 1):
                if max(abs(grid_x), abs(grid_y)) != ring:
                    continue
                x = round(producer.x + grid_x * step)
                y = round(producer.y + grid_y * step)
                distance_squared = (x - producer.x) ** 2 + (y - producer.y) ** 2
                if clearance**2 <= distance_squared <= MAX_SPAWN_SEARCH_RADIUS**2:
                    candidates.append((distance_squared, y, x))

    for _, y, x in sorted(set(candidates)):
        point = (x, y)
        if _is_valid_spawn(state, producer, definition.radius, point):
            return point
    return None


def _is_valid_spawn(
    state: GameState,
    producer: Building,
    radius: float,
    point: tuple[int, int],
) -> bool:
    x, y = point
    if x - radius < 0 or y - radius < 0:
        return False
    if x + radius > state.map_width or y + radius > state.map_height:
        return False
    if state.terrain.blocks_movement(point, radius=radius):
        return False

    for entity in state.store:
        if entity is producer or entity.life <= 0 or not isinstance(entity, (Unit, Building)):
            continue
        min_distance = radius + entity.radius + 2
        dx = x - entity.x
        dy = y - entity.y
        if dx * dx + dy * dy < min_distance * min_distance:
            return False
    return True
