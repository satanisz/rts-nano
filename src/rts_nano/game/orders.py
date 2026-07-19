"""Order application helpers for game and headless callers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.order import MAX_QUEUED_ORDERS, Order, OrderKind
from rts_nano.game.rules import distance_between_points, nearest_entity
from rts_nano.simulation.entities.base import Building, Resource, Unit
from rts_nano.simulation.entities.buildings import Base
from rts_nano.simulation.entities.units import Peasant

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rts_nano.game.construction import ConstructionSystem
    from rts_nano.game.movement import MovementSystem
    from rts_nano.game.production import ProductionSystem
    from rts_nano.game.state import GameState
    from rts_nano.game.types import EntityId
    from rts_nano.simulation.entities import TeamColor
    from rts_nano.simulation.entities.base import Entity


class OrderSystem:
    """Apply high-level unit, building, and selection orders over the game state."""

    def __init__(
        self,
        state: GameState,
        movement: MovementSystem,
        production: ProductionSystem,
        construction: ConstructionSystem,
    ) -> None:
        """Initialize the order system with the state and collaborator systems."""
        self._state = state
        self._movement = movement
        self._production = production
        self._construction = construction
        self._queued_units: dict[EntityId, Unit] = {}

    def units_for_team(self, team: TeamColor) -> list[Unit]:
        """Return all living units owned by a team."""
        return self._state.units_for_team(team)

    def bases_for_team(self, team: TeamColor) -> list[Base]:
        """Return all bases owned by a team."""
        return [base for base in self._state.entities_by_content_id("base", team=team) if isinstance(base, Base)]

    def carrying_peasants_for_team(self, team: TeamColor) -> list[Peasant]:
        """Return living team peasants that currently carry resources."""
        return [
            unit
            for unit in self.units_for_team(team)
            if isinstance(unit, Peasant) and (unit.carry_wood > 0 or unit.carry_gold > 0)
        ]

    def production_buildings_for_team(self, team: TeamColor) -> list[Building]:
        """Return production-capable buildings owned by a team."""
        return [building for building in self._state.buildings_for_team(team) if building.definition.produces]

    def issue_move_order(
        self,
        team: TeamColor,
        destination: tuple[float, float],
        units: Iterable[Unit] | None = None,
        *,
        queue: bool = False,
    ) -> int:
        """Assign a move order to team units and return the affected count."""
        ordered_units = self._order_units_for_team(team, units)
        assignments = self._movement.group_move_assignments(ordered_units, (int(destination[0]), int(destination[1])))
        return sum(self._queue_or_execute(unit, Order("move", slot), queue=queue) for unit, slot in assignments)

    def issue_attack_move_order(
        self,
        team: TeamColor,
        destination: tuple[float, float],
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Move team units while allowing them to acquire hostile targets."""
        ordered_units = self._order_units_for_team(team, units)
        if not ordered_units:
            return 0

        self._tag_order(ordered_units, "attack_move", destination)
        center = (int(destination[0]), int(destination[1]))
        clicked_target = next(
            (
                entity
                for entity in self._state.store
                if isinstance(entity, (Unit, Building))
                and entity.team != team
                and entity.life > 0
                and entity.contains_point(center)
            ),
            None,
        )
        slots = self._movement.formation_destinations(center, len(ordered_units))
        remaining_slots = slots.copy()
        for unit in sorted(
            ordered_units,
            key=lambda selected_unit: distance_between_points(selected_unit.get_center(), center),
        ):
            slot = min(remaining_slots, key=lambda candidate: distance_between_points(unit.get_center(), candidate))
            remaining_slots.remove(slot)
            target_point = clicked_target.get_center() if clicked_target is not None else slot
            if self._movement.assign_unit_target(unit, target_point, clicked_target):
                unit.attack_move_destination = slot
        return len(ordered_units)

    def issue_patrol_order(
        self,
        team: TeamColor,
        destination: tuple[float, float],
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Patrol team units between their current position and a destination.

        Patrol reuses the attack-move acquisition machinery by keeping
        ``attack_move_destination`` pointed at the active leg, and stores the two
        waypoints in ``patrol_points`` so the manager can flip legs on arrival.
        """
        ordered_units = self._order_units_for_team(team, units)
        if not ordered_units:
            return 0

        dest = (int(destination[0]), int(destination[1]))
        self._tag_order(ordered_units, "patrol", dest)
        for unit in ordered_units:
            origin = unit.get_center()
            unit.patrol_points = (origin, dest)
            if self._movement.assign_unit_target(unit, dest):
                unit.attack_move_destination = dest
            else:
                unit.patrol_points = None
        return len(ordered_units)

    def issue_target_order(
        self,
        team: TeamColor,
        target: Entity,
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Assign a target interaction order and return the affected count."""
        ordered_units = self._order_units_for_team(team, units)
        target_center = target.get_center()
        hostile = getattr(target, "team", team) != team
        self._tag_order(ordered_units, "attack" if hostile else "move", target_center)
        for unit in ordered_units:
            self._movement.assign_unit_target(unit, target_center, target)
        return len(ordered_units)

    def issue_gather_order(
        self,
        team: TeamColor,
        resource: Resource,
        units: Iterable[Unit] | None = None,
        *,
        queue: bool = False,
    ) -> int:
        """Order team peasants to gather from a resource node."""
        if resource.amount <= 0:
            return 0
        ordered_peasants = [unit for unit in self._order_units_for_team(team, units) if isinstance(unit, Peasant)]
        if resource.entity_id is None:
            return 0
        order = Order("gather", resource.get_center(), resource.entity_id)
        return sum(self._queue_or_execute(peasant, order, queue=queue) for peasant in ordered_peasants)

    def issue_stop_order(self, team: TeamColor, units: Iterable[Unit] | None = None) -> int:
        """Stop team units and clear their active targets."""
        ordered_units = self._order_units_for_team(team, units)
        self._tag_order(ordered_units, "stop")
        for unit in ordered_units:
            unit.target_entity = None
            unit.source_resource = None
            unit.attack_move_destination = None
            unit.path.clear()
            unit.state = "IDLE"
        return len(ordered_units)

    def issue_hold_order(self, team: TeamColor, units: Iterable[Unit] | None = None) -> int:
        """Hold team units in place and clear their active targets."""
        ordered_units = self._order_units_for_team(team, units)
        self._tag_order(ordered_units, "hold")
        for unit in ordered_units:
            unit.target_entity = None
            unit.source_resource = None
            unit.attack_move_destination = None
            unit.path.clear()
            unit.state = "HOLDING"
        return len(ordered_units)

    def issue_return_cargo_order(
        self,
        team: TeamColor,
        units: Iterable[Unit] | None = None,
        base: Base | None = None,
    ) -> int:
        """Order carrying peasants to deposit resources at an allied base."""
        if base is not None:
            if base.team != team or base.life <= 0 or base.is_under_construction:
                return 0
            bases = [base]
        else:
            bases = [candidate for candidate in self.bases_for_team(team) if not candidate.is_under_construction]
        if not bases:
            return 0

        ordered_peasants = [
            unit
            for unit in self._order_units_for_team(team, units)
            if isinstance(unit, Peasant) and (unit.carry_wood > 0 or unit.carry_gold > 0)
        ]
        self._tag_order(ordered_peasants, "return_cargo")
        affected = 0
        for peasant in ordered_peasants:
            target_base = base if base is not None else nearest_entity(peasant, bases)
            if target_base is None:
                continue
            self._movement.assign_unit_target(peasant, target_base.get_center(), target_base)
            affected += 1
        return affected

    def build_peasant(self, base: Base) -> bool:
        """Attempt to queue a Peasant at the given base."""
        return self.produce_unit(base, "peasant")

    def produce_unit(self, producer: Building, unit_type: str) -> bool:
        """Attempt to queue a unit at a production building."""
        return self._production.enqueue_unit(producer, unit_type)

    def construct_building(self, builder: Peasant, building_type: str, position: tuple[float, float]) -> bool:
        """Attempt to place a new building and assign a worker to construct it."""
        return self._construction.start_construction(builder, building_type, position) is not None

    def cancel_construction(self, building: Building) -> bool:
        """Attempt to cancel an unfinished building."""
        return self._construction.cancel_construction(building)

    def cancel_peasant_production(self, base: Base) -> bool:
        """Attempt to cancel the active Peasant production job at a base."""
        return self.cancel_production(base)

    def cancel_production(self, producer: Building) -> bool:
        """Attempt to cancel the active production job at a building."""
        return self._production.cancel_next(producer)

    def update_queues(self) -> None:
        """Start queued orders when a unit's active order has completed."""
        for entity_id, unit in tuple(self._queued_units.items()):
            if unit.life <= 0 or not unit.order_queue:
                del self._queued_units[entity_id]
                continue
            if self._has_active_order(unit):
                continue
            while unit.order_queue:
                order = unit.order_queue.pop(0)
                if self._execute_order(unit, order, clear_queue=False):
                    break
            if not unit.order_queue:
                del self._queued_units[entity_id]

    def _queue_or_execute(self, unit: Unit, order: Order, *, queue: bool) -> int:
        if queue and self._has_active_order(unit):
            if unit.entity_id is None or len(unit.order_queue) >= MAX_QUEUED_ORDERS:
                return 0
            unit.order_queue.append(order)
            self._queued_units[unit.entity_id] = unit
            return 1
        return int(self._execute_order(unit, order, clear_queue=True))

    def _execute_order(self, unit: Unit, order: Order, *, clear_queue: bool) -> bool:
        if clear_queue:
            unit.order_queue.clear()
            if unit.entity_id is not None:
                self._queued_units.pop(unit.entity_id, None)
        unit.current_order = order
        unit.patrol_points = None
        if order.kind == "move" and order.destination is not None:
            return self._movement.assign_unit_target(unit, order.destination)
        if order.kind == "gather" and order.target_entity_id is not None and isinstance(unit, Peasant):
            try:
                target = self._state.store.get(order.target_entity_id)
            except KeyError:
                return False
            if not isinstance(target, Resource) or target.amount <= 0:
                return False
            return self._movement.assign_unit_target(unit, target.get_center(), target)
        return False

    @staticmethod
    def _has_active_order(unit: Unit) -> bool:
        if unit.current_order is None:
            return False
        if unit.current_order.kind == "gather" and isinstance(unit, Peasant):
            return (
                unit.state in {"MOVING", "GATHERING", "DEPOSITING"}
                or unit.target_entity is not None
                or unit.source_resource is not None
                or unit.carry_wood > 0
                or unit.carry_gold > 0
            )
        return unit.state in {"MOVING", "ATTACKING", "BUILDING", "GATHERING", "DEPOSITING"}

    def _order_units_for_team(self, team: TeamColor, units: Iterable[Unit] | None = None) -> list[Unit]:
        """Normalize an optional unit iterable to units owned by a team."""
        source_units = self.units_for_team(team) if units is None else units
        return [unit for unit in source_units if unit.team == team and unit.life > 0]

    def _tag_order(
        self,
        units: Iterable[Unit],
        kind: OrderKind,
        destination: tuple[float, float] | None = None,
    ) -> None:
        """Record the high-level intent on units and cancel any active patrol.

        Patrol is the only order that keeps ``patrol_points`` set, so every other
        order clears it here. This keeps a manual command an unambiguous override
        of an in-progress patrol without touching the low-level state machine.
        """
        for unit in units:
            unit.order_queue.clear()
            if unit.entity_id is not None:
                self._queued_units.pop(unit.entity_id, None)
            unit.current_order = Order(kind, destination)
            if kind != "patrol":
                unit.patrol_points = None
