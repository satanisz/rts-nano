"""Pure game-rule helpers.

The entity objects keep mutable state, while this module keeps reusable rules
that do not need to know about pygame or rendering.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from rts_nano.game.assets.entities.base_entities import Entity, Resource


def distance_between(first: Entity, second: Entity) -> float:
    """Return center-to-center distance between two entities."""
    first_x, first_y = first.get_center()
    second_x, second_y = second.get_center()
    return math.hypot(second_x - first_x, second_y - first_y)


def distance_between_points(first: tuple[float, float], second: tuple[float, float]) -> float:
    """Return distance between two points."""
    return math.hypot(second[0] - first[0], second[1] - first[1])


def squared_distance_between(first: Entity, second: Entity) -> float:
    """Return squared center-to-center distance between two entities."""
    first_x, first_y = first.get_center()
    second_x, second_y = second.get_center()
    return (second_x - first_x) ** 2 + (second_y - first_y) ** 2


def calculate_damage(attack_damage: int, attack_modifier: int, shield_modifier: int) -> int:
    """Calculate effective damage after additive modifiers and shielding."""
    return max(0, attack_damage + attack_modifier - shield_modifier)


def clamp_point(
    point: tuple[float, float],
    *,
    min_x: float,
    max_x: float,
    min_y: float,
    max_y: float,
) -> tuple[float, float]:
    """Clamp a point to a rectangular play area."""
    x, y = point
    return min(max(x, min_x), max_x), min(max(y, min_y), max_y)


def nearest_entity(origin: Entity, entities: Sequence[Entity]) -> Entity | None:
    """Return the nearest entity to origin, or None when the sequence is empty."""
    if not entities:
        return None
    return min(entities, key=lambda entity: squared_distance_between(origin, entity))


def find_replacement_resource(
    depleted_resource: Resource,
    candidates: Iterable[Resource],
    *,
    search_radius: float,
) -> Resource | None:
    """Find a nearby resource node of the same type after one is depleted."""
    nearest: Resource | None = None
    nearest_distance = search_radius

    for candidate in candidates:
        if candidate is depleted_resource or candidate.amount <= 0:
            continue

        distance = distance_between(depleted_resource, candidate)
        if distance < nearest_distance:
            nearest = candidate
            nearest_distance = distance

    return nearest
