"""Worker-driven building construction."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rts_nano.game.assets.entities.base_entities import Building, Entity, TeamColor
from rts_nano.game.assets.entities.buildings import Barracks, House, MageTower
from rts_nano.game.data import CONSTRUCTION_REFUND_RATIO, ResourceCost, get_building_spec
from rts_nano.game.rules import distance_between_points

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.units import Peasant
    from rts_nano.game.manager import EntitiesGroup, GameManager


class ConstructionSystem:
    """Place unfinished buildings and advance them with workers."""

    _BUILDING_FACTORIES: ClassVar[dict[str, type[Building]]] = {
        "barracks": Barracks,
        "house": House,
        "mage_tower": MageTower,
    }
    _BUILDING_ROSTERS: ClassVar[dict[str, str]] = {
        "barracks": "barracks",
        "house": "houses",
        "mage_tower": "mage_towers",
    }

    def __init__(self, manager: GameManager) -> None:
        """Initialize construction state for one manager."""
        self._manager = manager

    @classmethod
    def supported_building_types(cls) -> tuple[str, ...]:
        """Return building types currently supported by worker construction."""
        return tuple(cls._BUILDING_FACTORIES)

    def can_team_construct(self, team: TeamColor, building_type: str) -> tuple[bool, str | None]:
        """Return whether a team has builders and resources for a building."""
        try:
            spec = get_building_spec(building_type)
        except ValueError:
            return False, "unsupported_building"

        if building_type not in self._BUILDING_FACTORIES:
            return False, "unsupported_building"

        group = self._manager.entities.get(team)
        if group is None:
            return False, "missing_team"
        if not any(builder.life > 0 for builder in group.peasents):
            return False, "no_builder"
        if not self._can_pay(group.resources, spec.cost):
            return False, "insufficient_resources"
        return True, None

    def can_start_construction(
        self,
        builder: Peasant,
        building_type: str,
        position: tuple[float, float],
    ) -> tuple[bool, str | None]:
        """Return whether one worker can start building at a world position."""
        if builder.life <= 0:
            return False, "inactive_builder"

        can_construct, reason = self.can_team_construct(builder.team, building_type)
        if not can_construct:
            return False, reason

        factory = self._BUILDING_FACTORIES[building_type]
        preview = factory(int(position[0]), int(position[1]), builder.team)
        if not self._is_valid_placement(preview, ignore=builder):
            return False, "invalid_placement"
        return True, None

    def start_construction(
        self,
        builder: Peasant,
        building_type: str,
        position: tuple[float, float],
    ) -> Building | None:
        """Pay for, place, and assign a worker to construct a building."""
        can_start, _ = self.can_start_construction(builder, building_type, position)
        if not can_start:
            return None

        spec = get_building_spec(building_type)
        group = self._manager.entities[builder.team]
        self._pay(group.resources, spec.cost)

        factory = self._BUILDING_FACTORIES[building_type]
        building = factory(int(position[0]), int(position[1]), builder.team)
        building.start_construction(spec.build_frames)
        self._add_building_to_group(group, building_type, building)
        self._manager._assign_unit_target(builder, building.get_center(), building)
        return building

    def unfinished_buildings_for_team(self, team: TeamColor) -> list[Building]:
        """Return unfinished buildings owned by a team."""
        group = self._manager.entities.get(team)
        if group is None:
            return []
        return [
            entity
            for entity in group.all_entities
            if isinstance(entity, Building) and entity.life > 0 and entity.is_under_construction
        ]

    def cancel_construction(self, building: Building) -> bool:
        """Cancel an unfinished building and refund part of its cost."""
        if building.life <= 0 or not building.is_under_construction:
            return False

        group = self._manager.entities.get(building.team)
        if group is None:
            return False

        building_type = getattr(building, "spec_key", type(building).__name__.lower())
        try:
            spec = get_building_spec(building_type)
        except ValueError:
            return False

        if not self._remove_building_from_group(group, building_type, building):
            return False

        self._refund(group.resources, spec.cost)
        building.is_under_construction = False
        building.life = 0
        self._detach_builders(group, building)
        self._manager.selected_entities = [
            entity for entity in self._manager.selected_entities if entity is not building
        ]
        building.selected = False
        return True

    def update(self) -> None:
        """Advance unfinished buildings when workers are actively building them."""
        for group in self._manager.entities.values():
            for builder in group.peasents:
                target = builder.target_entity
                constructable_target = self._constructable_target(builder, target)
                if builder.state != "BUILDING" or constructable_target is None:
                    continue
                constructable_target.advance_construction()
                if not constructable_target.is_under_construction:
                    builder.state = "IDLE"
                    builder.target_entity = None

    def _is_valid_placement(self, building: Building, *, ignore: Entity | None = None) -> bool:
        center = building.get_center()
        half_size = building.size / 2
        if center[0] - half_size < 0 or center[1] - half_size < 0:
            return False
        if center[0] + half_size > self._manager.map_width or center[1] + half_size > self._manager.map_height:
            return False
        if self._manager.terrain.blocks_movement(center, radius=building.radius):
            return False

        for entity in self._manager.all_entities:
            if entity is ignore:
                continue
            min_distance = building.radius + entity.radius + 4
            if distance_between_points(center, entity.get_center()) < min_distance:
                return False
        return True

    @staticmethod
    def _constructable_target(builder: Peasant, target: object) -> Building | None:
        if (
            isinstance(target, Building)
            and target.team == builder.team
            and target.life > 0
            and target.is_under_construction
        ):
            return target
        return None

    @classmethod
    def _add_building_to_group(cls, group: EntitiesGroup, building_type: str, building: Building) -> None:
        roster_name = cls._BUILDING_ROSTERS[building_type]
        roster = getattr(group, roster_name)
        roster.append(building)

    @classmethod
    def _remove_building_from_group(cls, group: EntitiesGroup, building_type: str, building: Building) -> bool:
        roster_name = cls._BUILDING_ROSTERS.get(building_type)
        if roster_name is None:
            return False
        roster = getattr(group, roster_name)
        if building not in roster:
            return False
        roster.remove(building)
        return True

    @staticmethod
    def _detach_builders(group: EntitiesGroup, building: Building) -> None:
        for builder in group.peasents:
            if builder.target_entity is not building:
                continue
            builder.target_entity = None
            builder.path.clear()
            builder.state = "IDLE"

    @staticmethod
    def _can_pay(resources: dict[str, int], cost: ResourceCost) -> bool:
        return resources.get("wood", 0) >= cost.wood and resources.get("gold", 0) >= cost.gold

    @staticmethod
    def _pay(resources: dict[str, int], cost: ResourceCost) -> None:
        resources["wood"] = resources.get("wood", 0) - cost.wood
        resources["gold"] = resources.get("gold", 0) - cost.gold

    @staticmethod
    def _refund(resources: dict[str, int], cost: ResourceCost) -> None:
        resources["wood"] = resources.get("wood", 0) + int(cost.wood * CONSTRUCTION_REFUND_RATIO)
        resources["gold"] = resources.get("gold", 0) + int(cost.gold * CONSTRUCTION_REFUND_RATIO)
