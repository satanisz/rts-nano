"""Translate public environment action DTOs into game orders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.actions import (
    Action,
    AttackAction,
    BuildAction,
    DepositAction,
    GatherAction,
    MoveAction,
    NoOpAction,
    SelectAction,
)
from rts_nano.game.assets.entities.base_entities import Resource, Unit
from rts_nano.game.assets.entities.buildings import Base
from rts_nano.game.assets.entities.units import Peasant

if TYPE_CHECKING:
    from rts_nano.game.assets.entities import TeamColor
    from rts_nano.game.assets.entities.base_entities import Entity
    from rts_nano.game.manager import GameManager
    from rts_nano.game.observations import EntityId, EntityIdRegistry


class ActionTranslator:
    """Apply public action DTOs through the manager's order system."""

    def __init__(self, manager: GameManager, entity_ids: EntityIdRegistry) -> None:
        """Initialize the translator for one manager and entity ID registry."""
        self._manager = manager
        self._entity_ids = entity_ids

    def apply(self, action: Action) -> int:
        """Apply one action and return the number of affected entities."""
        if isinstance(action, NoOpAction):
            return 0
        if isinstance(action, MoveAction):
            return self._apply_move(action)
        if isinstance(action, AttackAction):
            return self._apply_attack(action)
        if isinstance(action, GatherAction):
            return self._apply_gather(action)
        if isinstance(action, DepositAction):
            return self._apply_deposit(action)
        if isinstance(action, BuildAction):
            return self._apply_build(action)
        if isinstance(action, SelectAction):
            return self._apply_select(action)
        return 0

    def _apply_move(self, action: MoveAction) -> int:
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_move_order(action.team, action.destination, units)

    def _apply_attack(self, action: AttackAction) -> int:
        target = self._entity_by_id(action.target_id)
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_target_order(action.team, target, units)

    def _apply_gather(self, action: GatherAction) -> int:
        resource = self._entity_by_id(action.resource_id)
        if not isinstance(resource, Resource):
            raise ValueError(f"Entity is not a resource: {action.resource_id}")
        peasants = [unit for unit in self._units_for_action(action.team, action.unit_ids) if isinstance(unit, Peasant)]
        return self._manager.orders.issue_target_order(action.team, resource, peasants)

    def _apply_deposit(self, action: DepositAction) -> int:
        base = self._base_for_action(action.team, action.base_id)
        if base is None:
            return 0
        peasants = [unit for unit in self._units_for_action(action.team, action.unit_ids) if isinstance(unit, Peasant)]
        return self._manager.orders.issue_target_order(action.team, base, peasants)

    def _apply_build(self, action: BuildAction) -> int:
        if action.unit_type != "peasant":
            raise ValueError(f"Unsupported unit type: {action.unit_type}")
        base = self._base_for_action(action.team, action.base_id)
        if base is None:
            return 0
        return int(self._manager.orders.build_peasant(base))

    def _apply_select(self, action: SelectAction) -> int:
        selected = tuple(self._entity_by_id(entity_id) for entity_id in action.entity_ids)
        return self._manager.orders.select_entities_for_team(action.team, selected)

    def _units_for_action(self, team: TeamColor, unit_ids: tuple[EntityId, ...]) -> list[Unit]:
        if unit_ids:
            units: list[Unit] = []
            for entity_id in unit_ids:
                entity = self._entity_by_id(entity_id)
                if isinstance(entity, Unit) and entity.team == team:
                    units.append(entity)
            return units
        return self._manager.orders.units_for_team(team)

    def _base_for_action(self, team: TeamColor, base_id: EntityId | None) -> Base | None:
        if base_id is not None:
            base = self._entity_by_id(base_id)
            if not isinstance(base, Base):
                raise ValueError(f"Entity is not a base: {base_id}")
            return base if base.team == team else None
        bases = self._manager.orders.bases_for_team(team)
        if not bases:
            return None
        return bases[0]

    def _entity_by_id(self, entity_id: EntityId) -> Entity:
        return self._entity_ids.entity_by_id(self._manager, entity_id)
