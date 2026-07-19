"""Worker-driven building construction."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rts_nano.content import CONSTRUCTION_REFUND_RATIO, CONTENT, ResourceCost
from rts_nano.game.assets.entities.base_entities import Building, Entity, TeamColor, visual_assets_enabled
from rts_nano.game.assets.entities.buildings import (
    Arsenal,
    Bastion,
    ChemVat,
    House,
    Pit,
    Spiker,
    Spire,
)
from rts_nano.game.data import faction_for_team
from rts_nano.game.rules import distance_between_points

if TYPE_CHECKING:
    from collections.abc import Callable

    from rts_nano.game.assets.entities.units import Peasant
    from rts_nano.game.movement import MovementSystem
    from rts_nano.game.state import EntitiesGroup, GameState


class ConstructionSystem:
    """Place unfinished buildings and advance them with workers."""

    _BUILDING_FACTORIES: ClassVar[dict[str, Callable[[int, int, TeamColor], Building]]] = {
        "house": House,
        # AEGIS (slot into the barracks/mage_tower/tower rosters via subclassing)
        "arsenal": Arsenal,
        "spire": Spire,
        "bastion": Bastion,
        # RUST
        "pit": Pit,
        "chem_vat": ChemVat,
        "spiker": Spiker,
    }
    _BUILDING_ROSTERS: ClassVar[dict[str, str]] = {
        "house": "houses",
        "arsenal": "barracks",
        "spire": "mage_towers",
        "bastion": "towers",
        "pit": "barracks",
        "chem_vat": "mage_towers",
        "spiker": "towers",
    }

    def __init__(self, state: GameState, movement: MovementSystem) -> None:
        """Initialize construction state for one game state."""
        self._state = state
        self._movement = movement

    @classmethod
    def supported_building_types(cls) -> tuple[str, ...]:
        """Return building types currently supported by worker construction."""
        return tuple(cls._BUILDING_FACTORIES)

    def can_team_construct(self, team: TeamColor, building_type: str) -> tuple[bool, str | None]:
        """Return whether a team has builders and resources for a building."""
        try:
            spec = CONTENT.get_building(building_type)
        except ValueError:
            return False, "unsupported_building"

        if building_type not in self._BUILDING_FACTORIES:
            return False, "unsupported_building"
        if spec.faction is not None and spec.faction != faction_for_team(team):
            return False, "wrong_faction"

        group = self._state.entities.get(team)
        if group is None:
            return False, "missing_team"
        if not any(builder.life > 0 for builder in group.peasents):
            return False, "no_builder"
        if not all(self._has_completed_building(group, required) for required in spec.requires):
            return False, "missing_tech"
        if not self._can_pay(group.resources, spec.cost):
            return False, "insufficient_resources"
        return True, None

    @staticmethod
    def _has_completed_building(group: EntitiesGroup, spec_key: str) -> bool:
        """Return whether a team owns a finished, living building of a given type."""
        buildings = (*group.bases, *group.barracks, *group.houses, *group.mage_towers, *group.towers)
        return any(
            getattr(building, "spec_key", "") == spec_key and building.life > 0 and not building.is_under_construction
            for building in buildings
        )

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
        with visual_assets_enabled(self._state.load_visuals):
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

        spec = CONTENT.get_building(building_type)
        group = self._state.entities[builder.team]
        self._pay(group.resources, spec.cost)

        factory = self._BUILDING_FACTORIES[building_type]
        with visual_assets_enabled(self._state.load_visuals):
            building = factory(int(position[0]), int(position[1]), builder.team)
        building.start_construction(spec.build_frames)
        self._add_building_to_group(group, building_type, building)
        self._movement.assign_unit_target(builder, building.get_center(), building)
        return building

    def unfinished_buildings_for_team(self, team: TeamColor) -> list[Building]:
        """Return unfinished buildings owned by a team."""
        group = self._state.entities.get(team)
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

        group = self._state.entities.get(building.team)
        if group is None:
            return False

        building_type = getattr(building, "spec_key", type(building).__name__.lower())
        try:
            spec = CONTENT.get_building(building_type)
        except ValueError:
            return False

        if not self._remove_building_from_group(group, building_type, building):
            return False

        self._refund(group.resources, spec.cost)
        building.is_under_construction = False
        building.life = 0
        self._detach_builders(group, building)
        self._state.selected_entities = [entity for entity in self._state.selected_entities if entity is not building]
        building.selected = False
        return True

    def update(self) -> None:
        """Advance unfinished buildings when workers are actively building them."""
        for group in self._state.entities.values():
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
