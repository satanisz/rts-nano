"""Lightweight production queues for trainable units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rts_nano.game.assets.entities import Archer, Knight, Mage, Peasant
from rts_nano.game.data import PRODUCTION_REFUND_RATIO, ResourceCost, UnitSpec, get_unit_spec

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import TeamColor, Unit
    from rts_nano.game.assets.entities.buildings import Base
    from rts_nano.game.manager import GameManager


@dataclass(slots=True)
class ProductionItem:
    """One queued unit production job."""

    unit_type: str
    remaining_frames: int
    total_frames: int

    @property
    def progress(self) -> float:
        """Return completion progress in the inclusive range [0.0, 1.0]."""
        if self.total_frames <= 0:
            return 1.0
        completed = self.total_frames - self.remaining_frames
        return min(1.0, max(0.0, completed / self.total_frames))


class ProductionSystem:
    """Own production queues and spawn completed units through the manager."""

    _UNIT_FACTORIES = {
        "peasant": Peasant,
        "knight": Knight,
        "archer": Archer,
        "mage": Mage,
    }

    def __init__(self, manager: GameManager) -> None:
        """Initialize production state for one manager."""
        self._manager = manager
        self._queues: dict[Base, list[ProductionItem]] = {}

    def queue_for(self, base: Base) -> tuple[ProductionItem, ...]:
        """Return the immutable production queue for a base."""
        return tuple(self._queues.get(base, ()))

    def queued_units_for_team(self, team: TeamColor) -> int:
        """Return queued unit count for a team."""
        return sum(len(queue) for base, queue in self._queues.items() if base.team == team and base.life > 0)

    def queued_population_for_team(self, team: TeamColor) -> int:
        """Return population reserved by queued units for a team."""
        total = 0
        for base, queue in self._queues.items():
            if base.team != team or base.life <= 0:
                continue
            for item in queue:
                total += get_unit_spec(item.unit_type).population
        return total

    def can_enqueue_unit(self, base: Base, unit_type: str = "peasant") -> tuple[bool, str | None]:
        """Return whether a base can queue a unit and, if not, why."""
        try:
            spec = get_unit_spec(unit_type)
        except ValueError:
            return False, "unsupported_unit"

        if spec.produced_at != "base":
            return False, "wrong_production_building"
        if base.life <= 0:
            return False, "inactive_building"

        team_group = self._manager.entities.get(base.team)
        if team_group is None:
            return False, "missing_team"

        if not self._can_pay(team_group.resources, spec.cost):
            return False, "insufficient_resources"

        reserved_population = self._manager._count_units(base.team) + self.queued_population_for_team(base.team)
        if reserved_population + spec.population > self._manager.population_cap_for_team(base.team):
            return False, "population_cap"

        return True, None

    def enqueue_unit(self, base: Base, unit_type: str = "peasant") -> bool:
        """Pay for and queue a unit from a base."""
        can_enqueue, _ = self.can_enqueue_unit(base, unit_type)
        if not can_enqueue:
            return False

        spec = get_unit_spec(unit_type)
        team_group = self._manager.entities[base.team]
        self._pay(team_group.resources, spec.cost)
        self._queues.setdefault(base, []).append(
            ProductionItem(
                unit_type=unit_type,
                remaining_frames=spec.production_frames,
                total_frames=spec.production_frames,
            )
        )
        return True

    def cancel_next(self, base: Base) -> bool:
        """Cancel the active production job and refund part of its cost."""
        queue = self._queues.get(base)
        if not queue:
            return False

        item = queue.pop(0)
        if not queue:
            del self._queues[base]

        team_group = self._manager.entities.get(base.team)
        if team_group is not None:
            self._refund(team_group.resources, get_unit_spec(item.unit_type).cost)
        return True

    def update(self) -> None:
        """Advance active queues and spawn completed jobs."""
        live_bases = {base for group in self._manager.entities.values() for base in group.bases if base.life > 0}
        for base in tuple(self._queues):
            if base not in live_bases:
                del self._queues[base]

        for base, queue in list(self._queues.items()):
            if not queue:
                continue
            current = queue[0]
            current.remaining_frames -= 1
            if current.remaining_frames <= 0:
                queue.pop(0)
                self._spawn_unit(base, get_unit_spec(current.unit_type))
            if not queue:
                del self._queues[base]

    @staticmethod
    def _can_pay(resources: dict[str, int], cost: ResourceCost) -> bool:
        return resources.get("wood", 0) >= cost.wood and resources.get("cristal", 0) >= cost.cristal

    @staticmethod
    def _pay(resources: dict[str, int], cost: ResourceCost) -> None:
        resources["wood"] = resources.get("wood", 0) - cost.wood
        resources["cristal"] = resources.get("cristal", 0) - cost.cristal

    @staticmethod
    def _refund(resources: dict[str, int], cost: ResourceCost) -> None:
        resources["wood"] = resources.get("wood", 0) + int(cost.wood * PRODUCTION_REFUND_RATIO)
        resources["cristal"] = resources.get("cristal", 0) + int(cost.cristal * PRODUCTION_REFUND_RATIO)

    def _spawn_unit(self, base: Base, spec: UnitSpec) -> None:
        team_group = self._manager.entities.get(base.team)
        if team_group is None:
            return

        unit_factory = self._UNIT_FACTORIES.get(spec.key)
        if unit_factory is None:
            return

        spawn_x, spawn_y = self._manager._clamp_to_world((base.x, base.y + base.size))
        unit: Unit = unit_factory(int(spawn_x), int(spawn_y), base.team)
        roster = getattr(team_group, spec.roster_attribute)
        roster.append(unit)
