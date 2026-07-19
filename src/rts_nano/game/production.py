"""Lightweight production queues for trainable units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rts_nano.content import CONTENT, PRODUCTION_REFUND_RATIO, ResourceCost, UnitDefinition
from rts_nano.game.assets.entities import (
    Arclight,
    Brute,
    Guardian,
    Marksman,
    Peasant,
    Ripper,
    Spitter,
)
from rts_nano.game.assets.entities.base_entities import visual_assets_enabled

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Building, TeamColor, Unit
    from rts_nano.game.state import GameState


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
        # AEGIS
        "marksman": Marksman,
        "guardian": Guardian,
        "arclight": Arclight,
        # RUST
        "ripper": Ripper,
        "spitter": Spitter,
        "brute": Brute,
    }

    def __init__(self, state: GameState) -> None:
        """Initialize production state for one game state."""
        self._state = state
        self._queues: dict[Building, list[ProductionItem]] = {}

    def queue_for(self, producer: Building) -> tuple[ProductionItem, ...]:
        """Return the immutable production queue for a production building."""
        return tuple(self._queues.get(producer, ()))

    def queued_units_for_team(self, team: TeamColor) -> int:
        """Return queued unit count for a team."""
        return sum(
            len(queue) for producer, queue in self._queues.items() if producer.team == team and producer.life > 0
        )

    def queued_population_for_team(self, team: TeamColor) -> int:
        """Return population reserved by queued units for a team."""
        total = 0
        for producer, queue in self._queues.items():
            if producer.team != team or producer.life <= 0:
                continue
            for item in queue:
                total += CONTENT.get_unit(item.unit_type).population
        return total

    def can_enqueue_unit(self, producer: Building, unit_type: str = "peasant") -> tuple[bool, str | None]:
        """Return whether a building can queue a unit and, if not, why."""
        try:
            spec = CONTENT.get_unit(unit_type)
        except ValueError:
            return False, "unsupported_unit"

        producer_key = self._producer_key(producer)
        try:
            producer_spec = CONTENT.get_building(producer_key)
        except ValueError:
            return False, "unsupported_building"

        if spec.produced_at != producer_key or spec.key not in producer_spec.produces:
            return False, "wrong_production_building"
        if producer.life <= 0 or producer.is_under_construction:
            return False, "inactive_building"

        team_group = self._state.entities.get(producer.team)
        if team_group is None:
            return False, "missing_team"

        if not self._can_pay(team_group.resources, spec.cost):
            return False, "insufficient_resources"

        reserved_population = self._state.count_units(producer.team) + self.queued_population_for_team(producer.team)
        if reserved_population + spec.population > self._state.population_cap_for_team(producer.team):
            return False, "population_cap"

        return True, None

    def enqueue_unit(self, producer: Building, unit_type: str = "peasant") -> bool:
        """Pay for and queue a unit from a production building."""
        can_enqueue, _ = self.can_enqueue_unit(producer, unit_type)
        if not can_enqueue:
            return False

        spec = CONTENT.get_unit(unit_type)
        team_group = self._state.entities[producer.team]
        self._pay(team_group.resources, spec.cost)
        self._queues.setdefault(producer, []).append(
            ProductionItem(
                unit_type=unit_type,
                remaining_frames=spec.production_frames,
                total_frames=spec.production_frames,
            )
        )
        return True

    def cancel_next(self, producer: Building) -> bool:
        """Cancel the active production job and refund part of its cost."""
        queue = self._queues.get(producer)
        if not queue:
            return False

        item = queue.pop(0)
        if not queue:
            del self._queues[producer]

        team_group = self._state.entities.get(producer.team)
        if team_group is not None:
            self._refund(team_group.resources, CONTENT.get_unit(item.unit_type).cost)
        return True

    def update(self) -> None:
        """Advance active queues and spawn completed jobs."""
        live_producers = {
            producer
            for group in self._state.entities.values()
            for producer in (*group.bases, *group.barracks, *group.mage_towers)
            if producer.life > 0 and not producer.is_under_construction
        }
        for producer in tuple(self._queues):
            if producer not in live_producers:
                del self._queues[producer]

        for producer, queue in list(self._queues.items()):
            if not queue:
                continue
            current = queue[0]
            current.remaining_frames -= 1
            if current.remaining_frames <= 0:
                queue.pop(0)
                self._spawn_unit(producer, CONTENT.get_unit(current.unit_type))
            if not queue:
                del self._queues[producer]

    @staticmethod
    def _can_pay(resources: dict[str, int], cost: ResourceCost) -> bool:
        return resources.get("wood", 0) >= cost.wood and resources.get("gold", 0) >= cost.gold

    @staticmethod
    def _pay(resources: dict[str, int], cost: ResourceCost) -> None:
        resources["wood"] = resources.get("wood", 0) - cost.wood
        resources["gold"] = resources.get("gold", 0) - cost.gold

    @staticmethod
    def _refund(resources: dict[str, int], cost: ResourceCost) -> None:
        resources["wood"] = resources.get("wood", 0) + int(cost.wood * PRODUCTION_REFUND_RATIO)
        resources["gold"] = resources.get("gold", 0) + int(cost.gold * PRODUCTION_REFUND_RATIO)

    def _spawn_unit(self, producer: Building, spec: UnitDefinition) -> None:
        team_group = self._state.entities.get(producer.team)
        if team_group is None:
            return

        unit_factory = self._UNIT_FACTORIES.get(spec.key)
        if unit_factory is None:
            return

        spawn_x, spawn_y = self._state.clamp_to_world((producer.x, producer.y + producer.size))
        with visual_assets_enabled(self._state.load_visuals):
            unit: Unit = unit_factory(int(spawn_x), int(spawn_y), producer.team)
        roster = getattr(team_group, spec.roster_attribute)
        roster.append(unit)

    @staticmethod
    def _producer_key(producer: Building) -> str:
        return getattr(producer, "spec_key", type(producer).__name__.lower())
