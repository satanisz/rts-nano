"""Pure game-rule helpers.

The entity objects keep mutable state, while this module keeps reusable rules
that do not need to know about pygame or rendering.

Keep functions here deterministic and side-effect free. They are good targets
for future unit tests and RL-facing simulations because they do not depend on
pygame surfaces, clocks, or event state.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rts_nano.game.constants import AttackType

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from rts_nano.game.assets.entities.base_entities import Entity, Resource

HIGH_GROUND_RANGED_DAMAGE_BONUS = 2
LOW_GROUND_RANGED_DAMAGE_PENALTY = 1
HIGH_GROUND_RANGED_RANGE_BONUS = 35


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
    """Calculate effective damage after additive modifiers and shielding.

    Combat balance currently uses additive modifiers rather than percentages.
    Damage is clamped at zero so high shield values cannot heal the target.
    """
    return max(0, attack_damage + attack_modifier - shield_modifier)


def calculate_height_damage_modifier(attacker_height: int, target_height: int, attack_type: AttackType) -> int:
    """Return ranged combat damage modifier from terrain height differences.

    Only ranged attacks care about terrain height. High-ground attackers gain a
    small damage bonus; low-ground attackers suffer a penalty when firing up.
    """
    if attack_type != AttackType.RANGED or attacker_height == target_height:
        return 0
    if attacker_height > target_height:
        return HIGH_GROUND_RANGED_DAMAGE_BONUS
    return -LOW_GROUND_RANGED_DAMAGE_PENALTY


def calculate_height_range_bonus(attacker_height: int, target_height: int, attack_type: AttackType) -> int:
    """Return extra ranged attack reach granted by higher ground."""
    if attack_type == AttackType.RANGED and attacker_height > target_height:
        return HIGH_GROUND_RANGED_RANGE_BONUS
    return 0


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
    """Find a nearby resource node after one is depleted.

    The manager calls this while a peasant is harvesting. The helper assumes the
    caller has already passed a candidate list of the same resource type, so it
    only filters depleted/self candidates and applies the search radius.
    """
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
