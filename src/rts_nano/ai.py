"""Simple scripted opponent using generic team and content queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.content import CONTENT
from rts_nano.game.constants import FOG_CELL_SIZE
from rts_nano.game.fog import FogOfWar
from rts_nano.game.rules import nearest_entity
from rts_nano.simulation.entities.base import Building, Resource, Unit
from rts_nano.simulation.entities.units import Peasant

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.simulation.entities import TeamColor
    from rts_nano.simulation.entities.buildings import Base

_FACTION_PLAN: dict[str, tuple[str, tuple[str, ...]]] = {
    "AEGIS": ("arsenal", ("guardian", "marksman")),
    "RUST": ("pit", ("ripper", "spitter")),
}


class ScriptedAI:
    """Baseline gather/build/train/attack loop."""

    ATTACK_FORCE_SIZE = 3

    def __init__(self, manager: GameSession, team: TeamColor, *, decision_interval: int = 15) -> None:
        """Initialize the AI from the team's explicit faction assignment."""
        self._manager = manager
        self._team = team
        self._decision_interval = max(1, decision_interval)
        self._frame = 0
        self._vision = FogOfWar(manager.map_width, manager.map_height)
        self._last_known_enemy_base: tuple[float, float] | None = None
        self._failed_scout_request: tuple[object, ...] | None = None
        faction_id = str(manager.state.faction_for_team(team))
        self._military_building, self._army_units = _FACTION_PLAN.get(faction_id, ("arsenal", ("guardian",)))

    def step(self) -> None:
        """Issue decisions on the configured cadence."""
        self._frame += 1
        if self._frame % self._decision_interval != 0 or self._manager.state.team(self._team) is None:
            return
        self._vision.update(self._manager.state.entities_for_team(self._team))
        self._refresh_enemy_base_memory()
        self._assign_idle_workers()
        self._build_military()
        self._train_army()
        self._launch_attack()

    def _workers(self) -> list[Peasant]:
        return [unit for unit in self._manager.units_for_team(self._team) if isinstance(unit, Peasant)]

    def _assign_idle_workers(self) -> None:
        resources = [
            node
            for node in (
                *self._manager.state.resources_by_content("wood"),
                *self._manager.state.resources_by_content("gold"),
            )
            if node.amount > 0 and self._vision.is_explored(*node.get_center())
        ]
        if not resources:
            return
        for peasant in self._workers():
            if peasant.state == "IDLE" and peasant.carry_wood == 0 and peasant.carry_gold == 0:
                target = nearest_entity(peasant, resources)
                if isinstance(target, Resource):
                    self._manager.issue_gather_order(self._team, target, [peasant])

    def _build_military(self) -> None:
        military = self._manager.state.entities_by_content_id(self._military_building, team=self._team)
        bases = self._manager.bases_for_team(self._team)
        workers = self._workers()
        if military or not bases or not workers:
            return
        can_construct, _ = self._manager.construction.can_team_construct(self._team, self._military_building)
        if not can_construct:
            return
        base = bases[0]
        builder = workers[0]
        for offset_x, offset_y in ((140, 0), (-140, 0), (0, 140), (0, -140)):
            if self._manager.construct_building(
                builder, self._military_building, (base.x + offset_x, base.y + offset_y)
            ):
                return

    def _train_army(self) -> None:
        for producer in self._manager.state.entities_by_content_id(self._military_building, team=self._team):
            if not isinstance(producer, Building):
                continue
            if producer.is_under_construction or len(self._manager.production.queue_for(producer)) >= 2:
                continue
            for unit_type in self._army_units:
                if self._manager.produce_unit(producer, unit_type):
                    break

    def _launch_attack(self) -> None:
        army: list[Unit] = [unit for unit in self._manager.units_for_team(self._team) if not isinstance(unit, Peasant)]
        if len(army) < self.ATTACK_FORCE_SIZE:
            free_supply = self._manager.population_cap_for_team(self._team) - self._manager.state.population_for_team(
                self._team
            )
            cheapest_army_supply = min(CONTENT.get_unit(unit_id).population for unit_id in self._army_units)
            if (
                not army
                or self._manager.production.queued_units_for_team(self._team)
                or free_supply >= cheapest_army_supply
            ):
                return
        if self._last_known_enemy_base is None:
            self._scout_unexplored(army)
            return
        idle = [unit for unit in army if unit.state in {"IDLE", "HOLDING"}]
        if idle:
            self._manager.issue_attack_move_order(self._team, self._last_known_enemy_base, idle)

    @property
    def known_enemy_base_position(self) -> tuple[float, float] | None:
        """Return only the last position legitimately observed by this AI."""
        return self._last_known_enemy_base

    def _refresh_enemy_base_memory(self) -> None:
        visible_bases: list[Base] = []
        for team in self._manager.teams:
            if team == self._team:
                continue
            visible_bases.extend(
                base
                for base in self._manager.bases_for_team(team)
                if base.life > 0 and self._vision.is_visible(*base.get_center())
            )
        if visible_bases:
            origin = self._manager.bases_for_team(self._team)
            anchor = origin[0] if origin else self._workers()[0] if self._workers() else visible_bases[0]
            target = nearest_entity(anchor, visible_bases)
            if target is not None:
                center = target.get_center()
                self._last_known_enemy_base = (float(center[0]), float(center[1]))
            return

        remembered = self._last_known_enemy_base
        if remembered is not None and self._vision.is_visible(*remembered):
            self._last_known_enemy_base = None

    def _scout_unexplored(self, army: list[Unit]) -> None:
        idle = [unit for unit in army if unit.state in {"IDLE", "HOLDING"}]
        if not idle:
            return
        scout = idle[0]
        destination = self._nearest_unexplored_point(scout.get_center())
        if destination is not None:
            # Only reuse a failed ground request. An entity entering the clicked
            # point may change attack-move target resolution and must be retried.
            has_target = any(
                isinstance(entity, (Unit, Building))
                and entity.team != self._team
                and entity.life > 0
                and entity.contains_point(destination)
                for entity in self._manager.all_entities
            )
            if (
                not has_target
                and scout.path_unreachable
                and self._failed_scout_request == self._scout_request_key(scout, destination)
            ):
                return
            self._manager.issue_attack_move_order(self._team, destination, [scout])
            self._failed_scout_request = (
                self._scout_request_key(scout, destination) if scout.path_unreachable and not has_target else None
            )

    def _scout_request_key(self, scout: Unit, destination: tuple[int, int]) -> tuple[object, ...]:
        """Fingerprint one failed request without retaining entities or unbounded history."""
        terrain = self._manager.terrain
        return (
            scout.entity_id,
            scout.get_center(),
            scout.radius,
            destination,
            self._manager.state.obstacle_revision,
            scout.current_order,
            tuple(scout.order_queue),
            scout.attack_move_destination,
            scout.patrol_points,
            tuple(terrain.water),
            tuple(terrain.high_ground),
            tuple(terrain.ramps),
            tuple(terrain.rocks),
        )

    def _nearest_unexplored_point(
        self,
        origin: tuple[int | float, int | float],
    ) -> tuple[int, int] | None:
        candidates: list[tuple[int, int]] = []
        for row, cells in enumerate(self._vision.grid):
            for col, state in enumerate(cells):
                if state != FogOfWar.UNEXPLORED:
                    continue
                point = (
                    min(self._manager.map_width - 1, int((col + 0.5) * FOG_CELL_SIZE)),
                    min(self._manager.map_height - 1, int((row + 0.5) * FOG_CELL_SIZE)),
                )
                if not self._manager.terrain.blocks_movement(point):
                    candidates.append(point)
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda point: ((point[0] - origin[0]) ** 2 + (point[1] - origin[1]) ** 2, point[1], point[0]),
        )
