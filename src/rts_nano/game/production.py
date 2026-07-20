"""Lightweight production queues for trainable units."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from rts_nano.content import CONTENT, PRODUCTION_REFUND_RATIO, ContentRegistry, ResourceCost, UnitDefinition
from rts_nano.game.entity_factory import EntityFactory
from rts_nano.game.spawning import find_spawn_point

if TYPE_CHECKING:
    from rts_nano.game.state import GameState
    from rts_nano.game.upgrades import UpgradeSystem
    from rts_nano.simulation.entities.base import Building, TeamColor, Unit


@dataclass(slots=True)
class ActivityItem:
    """One typed unit-production or research job in a building FIFO."""

    kind: str
    content_id: str
    remaining_frames: int
    total_frames: int

    @property
    def unit_type(self) -> str:
        """Compatibility access for existing unit-production callers."""
        return self.content_id if self.kind == "unit" else ""

    @property
    def upgrade_id(self) -> str:
        """Return the research ID for a research job."""
        return self.content_id if self.kind == "research" else ""

    @property
    def progress(self) -> float:
        """Return completion progress in the inclusive range [0.0, 1.0]."""
        if self.total_frames <= 0:
            return 1.0
        completed = self.total_frames - self.remaining_frames
        return min(1.0, max(0.0, completed / self.total_frames))


class ProductionSystem:
    """Own production queues and spawn completed units through the manager."""

    def __init__(
        self,
        state: GameState,
        upgrades: UpgradeSystem | None = None,
        registry: ContentRegistry = CONTENT,
    ) -> None:
        """Initialize production state for one game state."""
        self._state = state
        self._queues: dict[Building, list[ActivityItem]] = {}
        self._upgrades = upgrades
        self._registry = registry

    def queue_for(self, producer: Building) -> tuple[ActivityItem, ...]:
        """Return the immutable activity queue for a production building."""
        return tuple(self._queues.get(producer, ()))

    def queued_units_for_team(self, team: TeamColor) -> int:
        """Return queued unit count for a team."""
        return sum(
            sum(item.kind == "unit" for item in queue)
            for producer, queue in self._queues.items()
            if producer.team == team and producer.life > 0
        )

    def queued_population_for_team(self, team: TeamColor) -> int:
        """Return population reserved by queued units for a team."""
        total = 0
        for producer, queue in self._queues.items():
            if producer.team != team or producer.life <= 0:
                continue
            for item in queue:
                if item.kind == "unit":
                    total += self._registry.get_unit(item.content_id).population
        return total

    def can_enqueue_unit(self, producer: Building, unit_type: str = "peasant") -> tuple[bool, str | None]:
        """Return whether a building can queue a unit and, if not, why."""
        try:
            spec = self._registry.get_unit(unit_type)
        except ValueError:
            return False, "unsupported_unit"

        producer_key = self._producer_key(producer)
        try:
            producer_spec = self._registry.get_building(producer_key)
        except ValueError:
            return False, "unsupported_building"

        if spec.key not in producer_spec.produces:
            return False, "wrong_production_building"
        if producer.life <= 0 or producer.is_under_construction:
            return False, "inactive_building"

        team_state = self._state.team(producer.team)
        if team_state is None:
            return False, "missing_team"

        if not self._can_pay(team_state.resources, spec.cost):
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

        spec = self._registry.get_unit(unit_type)
        team_state = self._state.teams[producer.team]
        self._pay(team_state.resources, spec.cost)
        self._queues.setdefault(producer, []).append(
            ActivityItem(
                kind="unit",
                content_id=unit_type,
                remaining_frames=spec.production_frames,
                total_frames=spec.production_frames,
            )
        )
        return True

    def can_research(self, producer: Building, upgrade_id: str) -> tuple[bool, str | None]:
        """Return whether a team may atomically reserve and queue research."""
        if self._upgrades is None:
            return False, "research_unavailable"
        try:
            upgrade = self._registry.get_upgrade(upgrade_id)
            producer_spec = self._registry.get_building(self._producer_key(producer))
        except ValueError:
            return False, "unsupported_upgrade"
        if producer_spec.id not in upgrade.research_at:
            return False, "wrong_research_building"
        if producer.life <= 0 or producer.is_under_construction:
            return False, "inactive_building"
        team_state = self._state.team(producer.team)
        if team_state is None:
            return False, "missing_team"
        can_complete, reason = self._upgrades.can_complete(producer.team, upgrade_id)
        if not can_complete:
            return False, reason
        if any(str(item) == upgrade_id for item in team_state.reserved_upgrades):
            return False, "already_reserved"
        if upgrade.exclusive_group is not None:
            for reserved_id in team_state.reserved_upgrades:
                reserved = self._registry.get_upgrade(str(reserved_id))
                if reserved.exclusive_group == upgrade.exclusive_group:
                    return False, "exclusive_choice_reserved"
        if any(
            not self._has_completed_building(producer.team, str(building_id))
            for building_id in upgrade.required_buildings
        ):
            return False, "missing_building"
        if not self._can_pay(team_state.resources, upgrade.cost):
            return False, "insufficient_resources"
        return True, None

    def enqueue_research(self, producer: Building, upgrade_id: str) -> bool:
        """Reserve, pay for, and append research to the building activity queue."""
        can_research, _ = self.can_research(producer, upgrade_id)
        if not can_research:
            return False
        upgrade = self._registry.get_upgrade(upgrade_id)
        team_state = self._state.teams[producer.team]
        if not team_state.reserve_upgrade(upgrade.id):
            return False
        self._pay(team_state.resources, upgrade.cost)
        self._queues.setdefault(producer, []).append(
            ActivityItem("research", upgrade_id, upgrade.research_frames, upgrade.research_frames)
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

        team_state = self._state.team(producer.team)
        if team_state is not None:
            if item.kind == "unit":
                self._refund(team_state.resources, self._registry.get_unit(item.content_id).cost)
            else:
                team_state.release_upgrade(item.content_id)
                self._refund(team_state.resources, self._registry.get_upgrade(item.content_id).cost)
        return True

    def update(self) -> tuple[tuple[Building, Unit], ...]:
        """Advance queues and return producer/unit pairs spawned this tick."""
        if not self._queues:
            return ()
        spawned: list[tuple[Building, Unit]] = []
        live_producers = {
            producer
            for team in self._state.teams
            for producer in self._state.buildings_for_team(team)
            if producer.life > 0 and not producer.is_under_construction
        }
        for producer in tuple(self._queues):
            if producer not in live_producers:
                self._release_destroyed_research(producer)
                del self._queues[producer]

        for producer, queue in list(self._queues.items()):
            if not queue:
                continue
            current = queue[0]
            current.remaining_frames = max(0, current.remaining_frames - 1)
            if current.remaining_frames <= 0:
                if current.kind == "unit":
                    unit = self._spawn_unit(producer, self._registry.get_unit(current.content_id))
                    if unit is not None:
                        spawned.append((producer, unit))
                        queue.pop(0)
                else:
                    if self._complete_research(producer, current.content_id):
                        queue.pop(0)
            if not queue:
                del self._queues[producer]
        return tuple(spawned)

    def _complete_research(self, producer: Building, upgrade_id: str) -> bool:
        team_state = self._state.team(producer.team)
        if team_state is None or self._upgrades is None:
            return False
        completed = self._upgrades.complete(producer.team, upgrade_id)
        if completed:
            team_state.release_upgrade(upgrade_id)
        return completed

    def _release_destroyed_research(self, producer: Building) -> None:
        team_state = self._state.team(producer.team)
        if team_state is None:
            return
        for item in self._queues.get(producer, ()):
            if item.kind == "research":
                team_state.release_upgrade(item.content_id)

    def _has_completed_building(self, team: TeamColor, content_id: str) -> bool:
        return any(
            building.life > 0 and not getattr(building, "is_under_construction", True)
            for building in self._state.entities_by_content_id(content_id, team=team)
        )

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

    def _spawn_unit(self, producer: Building, spec: UnitDefinition) -> Unit | None:
        if self._state.team(producer.team) is None:
            return None

        spawn_point = find_spawn_point(self._state, producer, spec)
        if spawn_point is None:
            return None
        spawn_x, spawn_y = spawn_point
        unit = cast("Unit", EntityFactory.create(spec.key, int(spawn_x), int(spawn_y), producer.team))
        self._state.add_runtime_entity(unit)
        if self._upgrades is not None:
            self._upgrades.apply_to_entity(unit)
        return unit

    @staticmethod
    def _producer_key(producer: Building) -> str:
        return getattr(producer, "spec_key", type(producer).__name__.lower())
