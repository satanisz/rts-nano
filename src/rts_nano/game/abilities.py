"""Pure deterministic cast validation, movement, payment, and effect dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.content import CONTENT, ContentRegistry
from rts_nano.game.rules import apply_damage, distance_between_points
from rts_nano.game.types import AbilityEffectKind, AbilityTargetKind
from rts_nano.simulation.entities.units import CasterUnit

if TYPE_CHECKING:
    from rts_nano.content import AbilityDefinition
    from rts_nano.game.movement import MovementSystem
    from rts_nano.game.order import Order
    from rts_nano.game.state import GameState
    from rts_nano.simulation.entities import TeamColor
    from rts_nano.simulation.entities.base import Entity, Unit


class AbilitySystem:
    """Process only units carrying active cast orders; idle casters add no global scan."""

    def __init__(
        self,
        state: GameState,
        movement: MovementSystem,
        registry: ContentRegistry = CONTENT,
    ) -> None:
        """Bind simulation state, deterministic movement, and content definitions."""
        self._state = state
        self._movement = movement
        self._registry = registry

    def available_abilities(self, caster: CasterUnit) -> tuple[AbilityDefinition, ...]:
        """Return team-unlocked abilities in canonical ID order."""
        team_state = self._state.team(caster.team)
        if team_state is None:
            return ()
        granted = {
            str(ability_id)
            for upgrade_id in team_state.completed_upgrades
            for ability_id in self._registry.get_upgrade(str(upgrade_id)).granted_abilities
        }
        return tuple(self._registry.get_ability(ability_id) for ability_id in sorted(granted))

    def can_issue(
        self,
        team: TeamColor,
        caster: Unit,
        ability_id: str,
        target: Entity | None,
        destination: tuple[float, float] | None,
    ) -> tuple[bool, str | None]:
        """Validate ownership, unlock, target kind, life, and target identity."""
        if not isinstance(caster, CasterUnit) or caster.team != team or caster.life <= 0:
            return False, "invalid_caster"
        try:
            ability = self._registry.get_ability(ability_id)
        except ValueError:
            return False, "unsupported_ability"
        if ability_id not in {str(item.id) for item in self.available_abilities(caster)}:
            return False, "locked_ability"
        if ability.target_kind == AbilityTargetKind.SELF:
            return (target in {None, caster}, None if target in {None, caster} else "invalid_target")
        if ability.target_kind in {AbilityTargetKind.GROUND, AbilityTargetKind.AREA}:
            return (destination is not None, None if destination is not None else "missing_destination")
        if target is None or target.life <= 0 or target.entity_id is None:
            return False, "invalid_target"
        is_ally = getattr(target, "team", None) == caster.team
        if ability.target_kind == AbilityTargetKind.ALLY and not is_ally:
            return False, "invalid_target"
        if ability.target_kind == AbilityTargetKind.ENEMY and is_ally:
            return False, "invalid_target"
        return True, None

    def start_order(self, caster: Unit, order: Order) -> bool:
        """Start a validated cast without paying energy or starting cooldown."""
        if not isinstance(caster, CasterUnit) or order.ability_id is None:
            return False
        target = self._target_for(order)
        can_issue, _ = self.can_issue(caster.team, caster, str(order.ability_id), target, order.destination)
        if not can_issue:
            return False
        caster.current_order = order
        caster.target_entity = None
        caster.source_resource = None
        destination = self._cast_position(caster, order, target)
        if destination is not None:
            self._movement.assign_unit_target(caster, destination)
        else:
            caster.state = "IDLE"
        return True

    def update_cast(self, caster: Unit) -> bool:
        """Advance one cast order and apply it exactly once when legal and in range."""
        if not isinstance(caster, CasterUnit):
            return False
        order = caster.current_order
        if order is None or order.kind != "cast" or order.ability_id is None:
            return False
        ability = self._registry.get_ability(str(order.ability_id))
        target = self._target_for(order)
        if not self._target_still_valid(caster, ability, target, order.destination):
            self._clear_order(caster)
            return False
        position = self._cast_position(caster, order, target)
        if position is None:
            self._clear_order(caster)
            return False
        cast_distance = distance_between_points(caster.get_center(), position)
        target_radius = getattr(target, "radius", 0)
        if cast_distance > ability.cast_range + caster.radius + target_radius:
            if distance_between_points((caster.target_x, caster.target_y), position) > max(1.0, caster.speed):
                self._movement.assign_unit_target(caster, position)
            return False
        if caster.energy < ability.energy_cost or caster.ability_cooldowns.get(str(ability.id), 0) > 0:
            caster.state = "IDLE"
            return False
        if not self._apply_effect(caster, ability, target, position):
            self._clear_order(caster)
            return False
        caster.energy -= ability.energy_cost
        caster.ability_cooldowns[str(ability.id)] = ability.cooldown_frames
        self._clear_order(caster)
        return True

    def _target_for(self, order: Order) -> Entity | None:
        if order.target_entity_id is None:
            return None
        try:
            return self._state.store.get(order.target_entity_id)
        except KeyError:
            return None

    @staticmethod
    def _cast_position(
        caster: CasterUnit,
        order: Order,
        target: Entity | None,
    ) -> tuple[float, float] | None:
        if target is not None:
            return target.get_center()
        if order.destination is not None:
            return order.destination
        if order.target_entity_id is None:
            return caster.get_center()
        return None

    @staticmethod
    def _target_still_valid(
        caster: CasterUnit,
        ability: AbilityDefinition,
        target: Entity | None,
        destination: tuple[float, float] | None,
    ) -> bool:
        if ability.target_kind == AbilityTargetKind.SELF:
            return caster.life > 0
        if ability.target_kind in {AbilityTargetKind.GROUND, AbilityTargetKind.AREA}:
            return destination is not None
        if target is None or target.life <= 0:
            return False
        is_ally = getattr(target, "team", None) == caster.team
        return (ability.target_kind == AbilityTargetKind.ALLY and is_ally) or (
            ability.target_kind == AbilityTargetKind.ENEMY and not is_ally
        )

    def _apply_effect(
        self,
        caster: CasterUnit,
        ability: AbilityDefinition,
        target: Entity | None,
        position: tuple[float, float],
    ) -> bool:
        del caster, position
        if ability.effect_kind == AbilityEffectKind.DIRECT_DAMAGE and target is not None:
            apply_damage(target, ability.magnitude)
            return True
        return False

    @staticmethod
    def _clear_order(caster: CasterUnit) -> None:
        caster.current_order = None
        caster.target_entity = None
        caster.path.clear()
        caster.state = "IDLE"
