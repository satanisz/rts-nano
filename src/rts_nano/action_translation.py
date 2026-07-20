"""Translate public environment action DTOs into game orders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.actions import (
    Action,
    AttackAction,
    AttackMoveAction,
    BuildAction,
    CancelConstructionAction,
    CancelProductionAction,
    ConstructAction,
    DepositAction,
    GatherAction,
    HoldAction,
    MoveAction,
    NoOpAction,
    PatrolAction,
    ReturnCargoAction,
    SelectAction,
    StopAction,
)
from rts_nano.simulation.entities.base import Building, Resource, Unit
from rts_nano.simulation.entities.buildings import Base
from rts_nano.simulation.entities.units import Peasant

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.game.observations import EntityId, EntityIdRegistry
    from rts_nano.simulation.entities import TeamColor
    from rts_nano.simulation.entities.base import Entity


class ActionTranslator:
    """Apply public action DTOs through the manager's order system."""

    def __init__(self, manager: GameSession, entity_ids: EntityIdRegistry) -> None:
        """Initialize the translator for one manager and entity ID registry."""
        self._manager = manager
        self._entity_ids = entity_ids

    def apply(self, action: Action) -> int:
        """Apply one action and return the number of affected entities."""
        if isinstance(action, NoOpAction):
            return 0
        if isinstance(action, MoveAction):
            return self._apply_move(action)
        if isinstance(action, AttackMoveAction):
            return self._apply_attack_move(action)
        if isinstance(action, PatrolAction):
            return self._apply_patrol(action)
        if isinstance(action, AttackAction):
            return self._apply_attack(action)
        if isinstance(action, GatherAction):
            return self._apply_gather(action)
        if isinstance(action, DepositAction):
            return self._apply_deposit(action)
        if isinstance(action, ReturnCargoAction):
            return self._apply_return_cargo(action)
        if isinstance(action, BuildAction):
            return self._apply_build(action)
        if isinstance(action, ConstructAction):
            return self._apply_construct(action)
        if isinstance(action, CancelConstructionAction):
            return self._apply_cancel_construction(action)
        if isinstance(action, CancelProductionAction):
            return self._apply_cancel_production(action)
        if isinstance(action, StopAction):
            return self._apply_stop(action)
        if isinstance(action, HoldAction):
            return self._apply_hold(action)
        if isinstance(action, SelectAction):
            return self._apply_select(action)
        return 0

    def validate(self, action: Action) -> tuple[bool, str | None]:
        """Validate an existing public action without mutating simulation state."""
        try:
            if isinstance(action, NoOpAction):
                return True, None
            if isinstance(action, (MoveAction, AttackMoveAction, PatrolAction, StopAction, HoldAction)):
                return self._availability(bool(self._units_for_action(action.team, action.unit_ids)), "no_units")
            if isinstance(action, AttackAction):
                target = self._entity_by_id(action.target_id)
                units = self._units_for_action(action.team, action.unit_ids)
                return self._availability(bool(units and getattr(target, "life", 0) > 0), "no_units_or_target")
            if isinstance(action, GatherAction):
                target = self._entity_by_id(action.resource_id)
                units = self._units_for_action(action.team, action.unit_ids)
                valid = (
                    isinstance(target, Resource)
                    and target.amount > 0
                    and any(isinstance(unit, Peasant) for unit in units)
                )
                return self._availability(valid, "no_peasant_or_resource")
            if isinstance(action, (DepositAction, ReturnCargoAction)):
                base_id = action.base_id
                base = self._base_for_action(action.team, base_id) if base_id is not None else None
                bases_exist = base is not None or bool(self._manager.orders.bases_for_team(action.team))
                units = self._units_for_action(action.team, action.unit_ids)
                return self._availability(
                    bases_exist and any(isinstance(unit, Peasant) for unit in units),
                    "no_peasant_or_base",
                )
            if isinstance(action, BuildAction):
                producer = self._producer_for_action(action.team, action.base_id, action.unit_type)
                if producer is None:
                    return False, "no_producer"
                return self._manager.production.can_enqueue_unit(producer, action.unit_type)
            if isinstance(action, ConstructAction):
                builder = self._builder_for_action(
                    action.team, action.builder_id, action.building_type, action.position
                )
                return self._availability(builder is not None, "cannot_construct")
            if isinstance(action, CancelConstructionAction):
                building = self._unfinished_building_for_action(action.team, action.building_id)
                return self._availability(building is not None, "no_unfinished_building")
            if isinstance(action, CancelProductionAction):
                producer = self._producer_for_action(action.team, action.base_id)
                return self._availability(producer is not None, "empty_queue")
            if isinstance(action, SelectAction):
                entities = tuple(self._entity_by_id(entity_id) for entity_id in action.entity_ids)
                return self._availability(
                    bool(entities) and all(getattr(entity, "team", None) == action.team for entity in entities),
                    "invalid_selection",
                )
        except KeyError, ValueError:
            return False, "invalid_entity"
        return False, "unsupported_action"

    @staticmethod
    def _availability(condition: bool, reason: str) -> tuple[bool, str | None]:
        return condition, None if condition else reason

    def _apply_move(self, action: MoveAction) -> int:
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_move_order(action.team, action.destination, units)

    def _apply_attack_move(self, action: AttackMoveAction) -> int:
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_attack_move_order(action.team, action.destination, units)

    def _apply_patrol(self, action: PatrolAction) -> int:
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_patrol_order(action.team, action.destination, units)

    def _apply_attack(self, action: AttackAction) -> int:
        target = self._entity_by_id(action.target_id)
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_target_order(action.team, target, units)

    def _apply_gather(self, action: GatherAction) -> int:
        resource = self._entity_by_id(action.resource_id)
        if not isinstance(resource, Resource):
            raise ValueError(f"Entity is not a resource: {action.resource_id}")
        peasants = [unit for unit in self._units_for_action(action.team, action.unit_ids) if isinstance(unit, Peasant)]
        return self._manager.orders.issue_gather_order(action.team, resource, peasants)

    def _apply_deposit(self, action: DepositAction) -> int:
        base = self._base_for_action(action.team, action.base_id)
        if base is None:
            return 0
        peasants = [unit for unit in self._units_for_action(action.team, action.unit_ids) if isinstance(unit, Peasant)]
        return self._manager.orders.issue_target_order(action.team, base, peasants)

    def _apply_return_cargo(self, action: ReturnCargoAction) -> int:
        base = self._base_for_action(action.team, action.base_id) if action.base_id is not None else None
        if action.base_id is not None and base is None:
            return 0
        peasants = [unit for unit in self._units_for_action(action.team, action.unit_ids) if isinstance(unit, Peasant)]
        return self._manager.orders.issue_return_cargo_order(action.team, peasants, base)

    def _apply_build(self, action: BuildAction) -> int:
        producer = self._producer_for_action(action.team, action.base_id, action.unit_type)
        if producer is None:
            return 0
        return int(self._manager.orders.produce_unit(producer, action.unit_type))

    def _apply_construct(self, action: ConstructAction) -> int:
        builder = self._builder_for_action(action.team, action.builder_id, action.building_type, action.position)
        if builder is None:
            return 0
        return int(self._manager.orders.construct_building(builder, action.building_type, action.position))

    def _apply_cancel_construction(self, action: CancelConstructionAction) -> int:
        building = self._unfinished_building_for_action(action.team, action.building_id)
        if building is None:
            return 0
        return int(self._manager.orders.cancel_construction(building))

    def _apply_cancel_production(self, action: CancelProductionAction) -> int:
        producer = self._producer_for_action(action.team, action.base_id)
        if producer is None:
            return 0
        return int(self._manager.orders.cancel_production(producer))

    def _apply_stop(self, action: StopAction) -> int:
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_stop_order(action.team, units)

    def _apply_hold(self, action: HoldAction) -> int:
        units = self._units_for_action(action.team, action.unit_ids)
        return self._manager.orders.issue_hold_order(action.team, units)

    def _apply_select(self, action: SelectAction) -> int:
        selected = tuple(self._entity_by_id(entity_id) for entity_id in action.entity_ids)
        return self._manager.select_entities_for_team(action.team, selected)

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

    def _producer_for_action(
        self,
        team: TeamColor,
        producer_id: EntityId | None,
        unit_type: str | None = None,
    ) -> Building | None:
        if producer_id is not None:
            producer = self._entity_by_id(producer_id)
            if not isinstance(producer, Building):
                raise ValueError(f"Entity is not a production building: {producer_id}")
            return producer if producer.team == team else None

        producers = self._manager.orders.production_buildings_for_team(team)
        if unit_type is None:
            return next((producer for producer in producers if self._manager.production.queue_for(producer)), None)
        return next(
            (producer for producer in producers if self._manager.production.can_enqueue_unit(producer, unit_type)[0]),
            None,
        )

    def _builder_for_action(
        self,
        team: TeamColor,
        builder_id: EntityId | None,
        building_type: str,
        position: tuple[float, float],
    ) -> Peasant | None:
        if builder_id is not None:
            builder = self._entity_by_id(builder_id)
            if not isinstance(builder, Peasant):
                raise ValueError(f"Entity is not a peasant builder: {builder_id}")
            return builder if builder.team == team else None

        return next(
            (
                unit
                for unit in self._manager.orders.units_for_team(team)
                if isinstance(unit, Peasant)
                and self._manager.construction.can_start_construction(unit, building_type, position)[0]
            ),
            None,
        )

    def _unfinished_building_for_action(
        self,
        team: TeamColor,
        building_id: EntityId | None,
    ) -> Building | None:
        if building_id is not None:
            building = self._entity_by_id(building_id)
            if not isinstance(building, Building):
                raise ValueError(f"Entity is not a building: {building_id}")
            if building.team != team or not building.is_under_construction:
                return None
            return building

        buildings = self._manager.construction.unfinished_buildings_for_team(team)
        if not buildings:
            return None
        return buildings[0]

    def _entity_by_id(self, entity_id: EntityId) -> Entity:
        return self._entity_ids.entity_by_id(self._manager, entity_id)
