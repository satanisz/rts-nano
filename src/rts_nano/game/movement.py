"""Unit movement, pathing, formation, and attack-move/patrol logic.

Extracted from ``GameManager`` so the tick's movement behavior lives in one
place. Map/terrain state comes from the shared ``GameState`` (``terrain``,
``map_width``/``map_height``, ``clamp_to_world``); the system owns target
assignment, A* pathing, formation spread, attack-move acquisition, patrol leg
flipping, and stuck recovery. Behavior is byte-identical to the previous
in-manager version.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import Building, Unit
from rts_nano.game.constants import (
    ATTACK_MOVE_MIN_ACQUIRE_RANGE,
    FORMATION_SPACING,
    STUCK_FRAME_LIMIT,
    STUCK_PROGRESS_DISTANCE,
    UNSTUCK_COOLDOWN_FRAMES,
)
from rts_nano.game.pathfinding import find_path
from rts_nano.game.rules import distance_between_points, nearest_entity
from rts_nano.game.types import EntityCategory

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Entity
    from rts_nano.game.state import GameState


class MovementSystem:
    """Own unit pathing, target assignment, and attack-move/patrol updates."""

    def __init__(self, state: GameState) -> None:
        """Initialize the movement system for one game state."""
        self._state = state

    def can_unit_move_to(self, unit: Unit, next_point: tuple[float, float]) -> bool:
        """Return whether terrain permits a unit movement step."""
        next_x, next_y = self._state.clamp_to_world(next_point)
        if not self._state.terrain.can_move_between(unit.get_center(), (next_x, next_y), radius=unit.radius):
            return False
        return not self._building_blocks_point(unit, (next_x, next_y), unit.target_entity)

    def find_unit_path(self, unit: Unit, destination: tuple[float, float]) -> list[tuple[float, float]]:
        """Build a terrain-aware path for a unit."""
        goal = self._state.clamp_to_world(destination)
        movement_cache: dict[tuple[tuple[float, float], tuple[float, float]], bool] = {}

        def can_move_between(current: tuple[float, float], next_point: tuple[float, float]) -> bool:
            key = (current, next_point)
            if key not in movement_cache:
                movement_cache[key] = self._state.terrain.can_move_between(
                    current, next_point, radius=unit.radius
                ) and not (self._building_blocks_segment(unit, current, next_point, unit.target_entity))
            return movement_cache[key]

        if can_move_between(unit.get_center(), goal):
            return [goal]

        return find_path(
            unit.get_center(),
            goal,
            width=self._state.map_width,
            height=self._state.map_height,
            can_move_between=can_move_between,
        )

    def attack_move_acquire_range(self, unit: Unit) -> float:
        """Return the exact center-query range used by attack-move acquisition."""
        return max(float(unit.vision_range), unit.attack_range + ATTACK_MOVE_MIN_ACQUIRE_RANGE)

    def _building_blocks_point(self, unit: Unit, point: tuple[float, float], target: Entity | None) -> bool:
        query_radius = unit.radius + self._state.spatial_index.max_radius
        for entity in self._state.spatial_index.query(point, query_radius):
            if not isinstance(entity, Building) or entity is target or entity.life <= 0:
                continue
            min_distance = unit.radius + entity.radius
            current_distance = distance_between_points(unit.get_center(), entity.get_center())
            next_distance = distance_between_points(point, entity.get_center())
            if next_distance < min_distance and next_distance <= current_distance:
                return True
        return False

    def _building_blocks_segment(
        self,
        unit: Unit,
        start: tuple[float, float],
        end: tuple[float, float],
        target: Entity | None,
    ) -> bool:
        """Return whether a path edge crosses a living non-target building."""
        for entity in self._state.store.by_category(EntityCategory.BUILDING):
            if entity is target or entity.life <= 0:
                continue
            center = entity.get_center()
            min_distance_squared = (unit.radius + entity.radius) ** 2
            start_distance_squared = distance_between_points(start, center) ** 2
            end_distance_squared = distance_between_points(end, center) ** 2
            escaping_overlap = (
                start_distance_squared < min_distance_squared and end_distance_squared > start_distance_squared
            )
            if not escaping_overlap and self._distance_squared_to_segment(center, start, end) < min_distance_squared:
                return True
        return False

    @staticmethod
    def _distance_squared_to_segment(
        point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]
    ) -> float:
        segment_x = end[0] - start[0]
        segment_y = end[1] - start[1]
        segment_length_squared = segment_x * segment_x + segment_y * segment_y
        if segment_length_squared == 0:
            return (point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2
        projection = ((point[0] - start[0]) * segment_x + (point[1] - start[1]) * segment_y) / segment_length_squared
        projection = min(1.0, max(0.0, projection))
        closest_x = start[0] + projection * segment_x
        closest_y = start[1] + projection * segment_y
        return (point[0] - closest_x) ** 2 + (point[1] - closest_y) ** 2

    def assign_unit_target(
        self,
        unit: Unit,
        destination: tuple[float, float],
        target_entity: Entity | None = None,
    ) -> None:
        """Assign a unit target plus an A* path when one is available."""
        unit.set_target(destination, target_entity)
        unit.set_path(self.find_unit_path(unit, destination))

    def assign_group_move_order(self, units: list[Unit], destination: tuple[int, int]) -> None:
        """Assign a ground move order, spreading units across formation slots."""
        if not units:
            return
        slots = self.formation_destinations(destination, len(units))
        remaining_slots = slots.copy()
        for unit in sorted(
            units, key=lambda selected_unit: distance_between_points(selected_unit.get_center(), destination)
        ):
            slot = min(remaining_slots, key=lambda candidate: distance_between_points(unit.get_center(), candidate))
            remaining_slots.remove(slot)
            self.assign_unit_target(unit, slot)

    def formation_destinations(self, center: tuple[int, int], count: int) -> list[tuple[int, int]]:
        """Return terrain-valid formation slots around a clicked ground point."""
        if count <= 1:
            return [center]

        columns = math.ceil(math.sqrt(count))
        rows = math.ceil(count / columns)
        offsets: list[tuple[float, float]] = []
        for row in range(rows):
            for column in range(columns):
                offset_x = (column - (columns - 1) / 2) * FORMATION_SPACING
                offset_y = (row - (rows - 1) / 2) * FORMATION_SPACING
                offsets.append((offset_x, offset_y))

        offsets.sort(key=lambda offset: offset[0] ** 2 + offset[1] ** 2)
        destinations: list[tuple[int, int]] = []
        for offset_x, offset_y in offsets[:count]:
            slot = self._state.clamp_to_world((center[0] + offset_x, center[1] + offset_y))
            if self._state.terrain.blocks_movement(slot):
                slot = center
            destinations.append(slot)
        return destinations

    def update_attack_move_target(self, unit: Unit, entities: list[Entity]) -> None:
        """Acquire a hostile target while an attack-move order is active."""
        destination = unit.attack_move_destination
        if destination is None or unit.target_entity is not None:
            return
        if unit.state not in {"MOVING", "IDLE"}:
            return

        target = self.nearest_attack_move_target(unit, entities)
        if target is None:
            return

        self.assign_unit_target(unit, target.get_center(), target)
        unit.attack_move_destination = destination

    def resume_or_finish_attack_move(self, unit: Unit) -> None:
        """Resume an attack-move route after combat or finish it at the goal."""
        destination = unit.attack_move_destination
        if destination is None or unit.target_entity is not None:
            return

        if distance_between_points(unit.get_center(), destination) <= max(unit.speed, 2):
            unit.attack_move_destination = None
            return

        if unit.state == "IDLE":
            self.assign_unit_target(unit, destination)
            unit.attack_move_destination = destination

    def update_patrol(self, unit: Unit) -> None:
        """Flip a patrolling unit to its other waypoint once a leg completes.

        Patrol reuses the attack-move acquisition pipeline, so while a leg is
        active (``attack_move_destination`` set) or the unit is fighting/moving,
        this does nothing. When the unit goes idle at a waypoint with no target,
        it heads to whichever patrol point is farther, producing a stable loop.
        """
        points = unit.patrol_points
        if points is None or unit.target_entity is not None:
            return
        if unit.attack_move_destination is not None or unit.state != "IDLE":
            return

        first_point, second_point = points
        current = unit.get_center()
        farther = (
            first_point
            if distance_between_points(current, first_point) >= distance_between_points(current, second_point)
            else second_point
        )
        self.assign_unit_target(unit, farther)
        unit.attack_move_destination = farther

    def nearest_attack_move_target(self, unit: Unit, entities: list[Entity]) -> Entity | None:
        """Return the nearest hostile unit/building in attack-move acquisition range."""
        acquire_range = self.attack_move_acquire_range(unit)
        candidates = [
            entity
            for entity in entities
            if entity is not unit
            and isinstance(entity, (Unit, Building))
            and entity.team != unit.team
            and entity.life > 0
            and distance_between_points(unit.get_center(), entity.get_center()) <= acquire_range
        ]
        return nearest_entity(unit, candidates)

    def update_unit_stuck_recovery(self, unit: Unit) -> None:
        """Recover units nudged off path by local collision resolution."""
        if unit.unstuck_cooldown > 0:
            unit.unstuck_cooldown -= 1

        if unit.state != "MOVING":
            unit.progress_anchor_x = unit.x
            unit.progress_anchor_y = unit.y
            unit.stuck_frames = 0
            return

        progress_distance = distance_between_points((unit.x, unit.y), (unit.progress_anchor_x, unit.progress_anchor_y))
        if progress_distance >= STUCK_PROGRESS_DISTANCE:
            unit.progress_anchor_x = unit.x
            unit.progress_anchor_y = unit.y
            unit.stuck_frames = 0
            return

        unit.stuck_frames += 1
        if unit.stuck_frames < STUCK_FRAME_LIMIT or unit.unstuck_cooldown > 0:
            return

        if unit.path:
            unit.path.pop(0)
        elif unit.target_entity and getattr(unit.target_entity, "life", 1) > 0:
            self.assign_unit_target(unit, unit.target_entity.get_center(), unit.target_entity)

        unit.progress_anchor_x = unit.x
        unit.progress_anchor_y = unit.y
        unit.stuck_frames = 0
        unit.unstuck_cooldown = UNSTUCK_COOLDOWN_FRAMES
