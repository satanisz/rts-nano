"""Order application helpers for game and headless callers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import Building, Entity, Unit

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

    def build_peasant(self, base: Base) -> bool:
        """Attempt to queue a Peasant at the given base."""
        return self.produce_unit(base, "peasant")

    def produce_unit(self, producer: Building, unit_type: str) -> bool:
        """Attempt to queue a unit at a production building."""
        return self._manager.production.enqueue_unit(producer, unit_type)

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
