"""Deterministic combat resolution for stationary attackers.

Unit combat still lives in ``Unit.update``. This system owns building-driven
attacks so defensive towers can fight without unit micromanagement, and it is
the first step toward extracting a full combat system out of ``GameManager``.

Damage is applied here deterministically; the manager turns the returned shot
descriptions into ranged projectile visuals, mirroring how unit ranged attacks
are rendered. Target acquisition is limited to a tower's own attack reach, which
is the practical equivalent of fog-aware targeting: a tower only fires at
enemies close enough to be within its line of sight.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.constants import FPS
from rts_nano.game.rules import (
    apply_damage,
    apply_poison,
    calculate_damage,
    combat_attack_bonus,
    combat_shield_modifier,
    distance_between,
    nearest_entity,
)
from rts_nano.game.types import EntityCategory
from rts_nano.simulation.entities.base import Building, Unit
from rts_nano.simulation.entities.buildings import Tower
from rts_nano.simulation.events import AttackLanded

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rts_nano.game.state import GameState
    from rts_nano.simulation.entities.base import Entity


class CombatSystem:
    """Resolve auto-attacks for stationary combat buildings such as towers."""

    def __init__(self, state: GameState) -> None:
        """Initialize the combat system for one game state."""
        self._state = state

    def update(self) -> list[AttackLanded]:
        """Advance tower cooldowns, fire at targets, and return shot visuals."""
        shots: list[AttackLanded] = []
        for attacker in self._attacking_buildings():
            if attacker.attack_cooldown > 0:
                attacker.attack_cooldown -= 1

            target = self._acquire_target(attacker)
            if target is None or attacker.attack_cooldown > 0:
                continue

            shots.append(self._fire(attacker, target))
        return shots

    def _attacking_buildings(self) -> Iterator[Tower]:
        """Yield completed, living towers able to attack this tick."""
        for building in self._state.store.by_category(EntityCategory.BUILDING):
            if (
                isinstance(building, Tower)
                and building.life > 0
                and not building.is_under_construction
                and building.attack_damage > 0
            ):
                yield building

    def _acquire_target(self, attacker: Tower) -> Entity | None:
        """Return the nearest hostile unit/building within attack reach."""
        reach = attacker.attack_range + attacker.radius
        nearby = self._state.spatial_index.query(attacker.get_center(), reach + self._state.spatial_index.max_radius)
        candidates = [
            entity
            for entity in nearby
            if isinstance(entity, (Unit, Building))
            and entity.team != attacker.team
            and entity.life > 0
            and distance_between(attacker, entity) <= reach + entity.radius
        ]
        return nearest_entity(attacker, candidates)

    def _fire(self, attacker: Tower, target: Entity) -> AttackLanded:
        """Apply deterministic damage and return a projectile description."""
        damage = calculate_damage(
            attacker.attack_damage,
            attacker.attack_modifier + combat_attack_bonus(attacker, target),
            combat_shield_modifier(target),
        )
        apply_damage(target, damage)
        apply_poison(target, attacker.poison_damage, attacker.poison_duration)
        attacker.attack_cooldown = max(1, int(attacker.attack_speed * FPS))
        if attacker.entity_id is None:
            raise RuntimeError("Tower must be registered before combat")
        return AttackLanded(
            attacker.entity_id,
            attacker.content_id,
            attacker.get_center(),
            target.get_center(),
            target,
        )
