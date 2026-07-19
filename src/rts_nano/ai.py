"""Simple scripted opponent using generic team and content queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.rules import nearest_entity
from rts_nano.simulation.entities.base import Building, Resource
from rts_nano.simulation.entities.units import Peasant

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.simulation.entities import TeamColor
    from rts_nano.simulation.entities.base import Unit
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
        faction_id = str(manager.state.faction_for_team(team))
        self._military_building, self._army_units = _FACTION_PLAN.get(faction_id, ("arsenal", ("guardian",)))

    def step(self) -> None:
        """Issue decisions on the configured cadence."""
        self._frame += 1
        if self._frame % self._decision_interval != 0 or self._manager.state.team(self._team) is None:
            return
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
            if node.amount > 0
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
            return
        target_base = self._enemy_base()
        if target_base is None:
            return
        idle = [unit for unit in army if unit.state in {"IDLE", "HOLDING"}]
        if idle:
            self._manager.issue_attack_move_order(self._team, target_base.get_center(), idle)

    def _enemy_base(self) -> Base | None:
        for team in self._manager.teams:
            if team == self._team:
                continue
            bases = self._manager.bases_for_team(team)
            if bases and bases[0].life > 0:
                return bases[0]
        return None
