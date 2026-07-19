"""Worker-driven building construction."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rts_nano.content import CONSTRUCTION_REFUND_RATIO, CONTENT, ResourceCost
from rts_nano.game.entity_factory import EntityFactory
from rts_nano.game.rules import distance_between_points
from rts_nano.simulation.entities.base import Building, Entity, TeamColor
from rts_nano.simulation.entities.units import Peasant

if TYPE_CHECKING:
    from rts_nano.game.movement import MovementSystem
    from rts_nano.game.state import GameState


class ConstructionSystem:
    """Place unfinished buildings and advance them with workers."""

    def __init__(self, state: GameState, movement: MovementSystem) -> None:
        """Initialize construction state for one game state."""
        self._state = state
        self._movement = movement

    @classmethod
    def supported_building_types(cls) -> tuple[str, ...]:
        """Return building types currently supported by worker construction."""
        return tuple(key for key, definition in CONTENT.buildings.items() if definition.constructable)

    def can_team_construct(self, team: TeamColor, building_type: str) -> tuple[bool, str | None]:
        """Return whether a team has builders and resources for a building."""
        try:
            spec = CONTENT.get_building(building_type)
        except ValueError:
            return False, "unsupported_building"

        if not spec.constructable:
            return False, "unsupported_building"
        if spec.faction is not None and spec.faction != self._state.faction_for_team(team):
            return False, "wrong_faction"

        team_state = self._state.team(team)
        if team_state is None:
            return False, "missing_team"
        if not any(builder.life > 0 for builder in self._builders_for_team(team)):
            return False, "no_builder"
        if not all(self._has_completed_building(team, str(required)) for required in spec.requires):
            return False, "missing_tech"
        if not self._can_pay(team_state.resources, spec.cost):
            return False, "insufficient_resources"
        return True, None

    def _has_completed_building(self, team: TeamColor, spec_key: str) -> bool:
        """Return whether a team owns a finished, living building of a given type."""
        return any(
            isinstance(building, Building) and building.life > 0 and not building.is_under_construction
            for building in self._state.entities_by_content_id(spec_key, team=team)
        )

    def _builders_for_team(self, team: TeamColor) -> list[Peasant]:
        return [
            entity for entity in self._state.entities_by_content_id("peasant", team=team) if isinstance(entity, Peasant)
        ]

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

        preview = cast(
            "Building", EntityFactory.create(building_type, int(position[0]), int(position[1]), builder.team)
        )
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

        spec = CONTENT.get_building(building_type)
        team_state = self._state.teams[builder.team]
        self._pay(team_state.resources, spec.cost)

        building = cast(
            "Building", EntityFactory.create(building_type, int(position[0]), int(position[1]), builder.team)
        )
        building.start_construction(spec.build_frames)
        self._state.store.add(building)
        self._movement.assign_unit_target(builder, building.get_center(), building)
        return building

    def unfinished_buildings_for_team(self, team: TeamColor) -> list[Building]:
        """Return unfinished buildings owned by a team."""
        if self._state.team(team) is None:
            return []
        return [
            entity
            for entity in self._state.buildings_for_team(team)
            if isinstance(entity, Building) and entity.life > 0 and entity.is_under_construction
        ]

    def cancel_construction(self, building: Building) -> bool:
        """Cancel an unfinished building and refund part of its cost."""
        if building.life <= 0 or not building.is_under_construction:
            return False

        team_state = self._state.team(building.team)
        if team_state is None:
            return False

        building_type = getattr(building, "spec_key", type(building).__name__.lower())
        try:
            spec = CONTENT.get_building(building_type)
        except ValueError:
            return False

        if not self._state.store.remove(building):
            return False

        self._refund(team_state.resources, spec.cost)
        building.is_under_construction = False
        building.life = 0
        self._detach_builders(building.team, building)
        self._state.selected_entities = [entity for entity in self._state.selected_entities if entity is not building]
        building.selected = False
        return True

    def update(self) -> None:
        """Advance unfinished buildings when workers are actively building them."""
        for team in self._state.teams:
            for builder in self._builders_for_team(team):
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
        if center[0] + half_size > self._state.map_width or center[1] + half_size > self._state.map_height:
            return False
        if self._state.terrain.blocks_movement(center, radius=building.radius):
            return False

        for entity in self._state.all_entities:
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

    def _detach_builders(self, team: TeamColor, building: Building) -> None:
        for builder in self._builders_for_team(team):
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
