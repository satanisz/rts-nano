"""A simple scripted AI opponent built on the public game API.

The AI makes every decision through the same public manager order/production
helpers a human or RL agent would use: gather with idle workers, build a single
barracks, train knights, then attack-move the enemy base once it has a force.
Because it touches economy, construction, production, and combat through the
public surface, it doubles as an end-to-end integration check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import Resource
from rts_nano.game.rules import nearest_entity

if TYPE_CHECKING:
    from rts_nano.game.assets.entities import TeamColor
    from rts_nano.game.assets.entities.buildings import Base
    from rts_nano.game.manager import GameManager
    from rts_nano.game.state import EntitiesGroup


class ScriptedAI:
    """Baseline opponent that runs a fixed gather/build/train/attack loop."""

    ATTACK_FORCE_SIZE = 3

    def __init__(self, manager: GameManager, team: TeamColor, *, decision_interval: int = 15) -> None:
        """Initialize the AI for one manager and team.

        Args:
            manager: Live game manager the AI observes and commands.
            team: Team the AI controls.
            decision_interval: Frames between AI decisions, to avoid spamming
                orders every tick.
        """
        self._manager = manager
        self._team = team
        self._decision_interval = max(1, decision_interval)
        self._frame = 0

    def step(self) -> None:
        """Advance the AI; issue orders on its decision cadence."""
        self._frame += 1
        if self._frame % self._decision_interval != 0:
            return
        group = self._manager.entities.get(self._team)
        if group is None:
            return
        self._assign_idle_workers(group)
        self._build_barracks(group)
        self._train_knights(group)
        self._launch_attack(group)

    def _assign_idle_workers(self, group: EntitiesGroup) -> None:
        resources = [
            node for node in (self._manager.resources.woods + self._manager.resources.golds) if node.amount > 0
        ]
        if not resources:
            return
        for peasant in group.peasents:
            if peasant.state == "IDLE" and peasant.carry_wood == 0 and peasant.carry_gold == 0:
                target = nearest_entity(peasant, resources)
                if isinstance(target, Resource):
                    self._manager.issue_gather_order(self._team, target, [peasant])

    def _build_barracks(self, group: EntitiesGroup) -> None:
        if group.barracks or not group.bases or not group.peasents:
            return
        can_construct, _ = self._manager.construction.can_team_construct(self._team, "barracks")
        if not can_construct:
            return
        base = group.bases[0]
        builder = group.peasents[0]
        for offset_x, offset_y in ((140, 0), (-140, 0), (0, 140), (0, -140)):
            if self._manager.construct_building(builder, "barracks", (base.x + offset_x, base.y + offset_y)):
                return

    def _train_knights(self, group: EntitiesGroup) -> None:
        for barracks in group.barracks:
            if barracks.is_under_construction:
                continue
            if len(self._manager.production.queue_for(barracks)) < 2:
                self._manager.produce_unit(barracks, "knight")

    def _launch_attack(self, group: EntitiesGroup) -> None:
        if len(group.knights) < self.ATTACK_FORCE_SIZE:
            return
        target_base = self._enemy_base()
        if target_base is None:
            return
        idle_knights = [knight for knight in group.knights if knight.state in {"IDLE", "HOLDING"}]
        if idle_knights:
            self._manager.issue_attack_move_order(self._team, target_base.get_center(), idle_knights)

    def _enemy_base(self) -> Base | None:
        for team, other_group in self._manager.entities.items():
            if team == self._team:
                continue
            for base in other_group.bases:
                if base.life > 0:
                    return base
        return None
