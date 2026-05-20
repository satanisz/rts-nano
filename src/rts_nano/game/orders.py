"""Order application helpers for game and headless callers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import Building, Entity, Unit
from rts_nano.game.assets.entities.units import Peasant
from rts_nano.game.rules import nearest_entity

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rts_nano.game.assets.entities import TeamColor
    from rts_nano.game.assets.entities.buildings import Base
    from rts_nano.game.manager import GameManager


class OrderSystem:
    """Apply high-level unit, building, and selection orders to a manager."""

    def __init__(self, manager: GameManager) -> None:
        """Initialize the order system for one game manager."""
        self._manager = manager

    def units_for_team(self, team: TeamColor) -> list[Unit]:
        """Return all living units owned by a team."""
        group = self._manager.entities.get(team)
        if group is None:
            return []
        return [*group.peasents, *group.knights, *group.archers, *group.mages]

    def bases_for_team(self, team: TeamColor) -> list[Base]:
        """Return all bases owned by a team."""
        group = self._manager.entities.get(team)
        if group is None:
            return []
        return group.bases.copy()

    def carrying_peasants_for_team(self, team: TeamColor) -> list[Peasant]:
        """Return living team peasants that currently carry resources."""
        return [
            unit
            for unit in self.units_for_team(team)
            if isinstance(unit, Peasant) and (unit.carry_wood > 0 or unit.carry_cristal > 0)
        ]

    def production_buildings_for_team(self, team: TeamColor) -> list[Building]:
        """Return production-capable buildings owned by a team."""
        group = self._manager.entities.get(team)
        if group is None:
            return []
        return [*group.bases, *group.barracks]

    def issue_move_order(
        self,
        team: TeamColor,
        destination: tuple[float, float],
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Assign a move order to team units and return the affected count."""
        ordered_units = self._order_units_for_team(team, units)
        self._manager._assign_group_move_order(ordered_units, (int(destination[0]), int(destination[1])))
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
        for unit in ordered_units:
            self._manager._assign_unit_target(unit, target_center, target)
        return len(ordered_units)

    def issue_stop_order(self, team: TeamColor, units: Iterable[Unit] | None = None) -> int:
        """Stop team units and clear their active targets."""
        ordered_units = self._order_units_for_team(team, units)
        for unit in ordered_units:
            unit.target_entity = None
            unit.source_resource = None
            unit.path.clear()
            unit.state = "IDLE"
        return len(ordered_units)

    def issue_hold_order(self, team: TeamColor, units: Iterable[Unit] | None = None) -> int:
        """Hold team units in place and clear their active targets."""
        ordered_units = self._order_units_for_team(team, units)
        for unit in ordered_units:
            unit.target_entity = None
            unit.source_resource = None
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
            if isinstance(unit, Peasant) and (unit.carry_wood > 0 or unit.carry_cristal > 0)
        ]
        affected = 0
        for peasant in ordered_peasants:
            target_base = base if base is not None else nearest_entity(peasant, bases)
            if target_base is None:
                continue
            self._manager._assign_unit_target(peasant, target_base.get_center(), target_base)
            affected += 1
        return affected

    def build_peasant(self, base: Base) -> bool:
        """Attempt to queue a Peasant at the given base."""
        return self.produce_unit(base, "peasant")

    def produce_unit(self, producer: Building, unit_type: str) -> bool:
        """Attempt to queue a unit at a production building."""
        return self._manager.production.enqueue_unit(producer, unit_type)

    def construct_building(self, builder: Peasant, building_type: str, position: tuple[float, float]) -> bool:
        """Attempt to place a new building and assign a worker to construct it."""
        return self._manager.construction.start_construction(builder, building_type, position) is not None

    def cancel_construction(self, building: Building) -> bool:
        """Attempt to cancel an unfinished building."""
        return self._manager.construction.cancel_construction(building)

    def cancel_peasant_production(self, base: Base) -> bool:
        """Attempt to cancel the active Peasant production job at a base."""
        return self.cancel_production(base)

    def cancel_production(self, producer: Building) -> bool:
        """Attempt to cancel the active production job at a building."""
        return self._manager.production.cancel_next(producer)

    def select_entities_for_team(self, team: TeamColor, entities: Iterable[Entity]) -> int:
        """Select team-owned units/buildings and return the selected count."""
        for entity in self._manager.all_entities:
            entity.selected = False
        self._manager.selected_entities.clear()

        for entity in entities:
            if getattr(entity, "team", None) == team and isinstance(entity, (Unit, Building)):
                entity.selected = True
                self._manager.selected_entities.append(entity)
        return len(self._manager.selected_entities)

    def _order_units_for_team(self, team: TeamColor, units: Iterable[Unit] | None = None) -> list[Unit]:
        """Normalize an optional unit iterable to units owned by a team."""
        source_units = self.units_for_team(team) if units is None else units
        return [unit for unit in source_units if unit.team == team and unit.life > 0]
