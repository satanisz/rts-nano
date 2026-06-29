"""A simple scripted AI opponent built on the public game API.

The AI makes every decision through the same public manager order/production
helpers a human or RL agent would use: gather with idle workers, raise its
faction's military building, train that faction's tier-1 army, then attack-move
the enemy base once it has a force. The build order is faction-aware (AEGIS
raises an arsenal and trains guardians/marksmen; RUST raises a pit and trains
rippers/spitters). Because it touches economy, construction, production, and
combat through the public surface, it doubles as an end-to-end integration check.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import Resource
from rts_nano.game.data import faction_for_team
from rts_nano.game.rules import nearest_entity

if TYPE_CHECKING:
    from rts_nano.game.assets.entities import TeamColor
    from rts_nano.game.assets.entities.buildings import Base
    from rts_nano.game.manager import GameManager
    from rts_nano.game.state import EntitiesGroup

# Per-faction tier-1 plan: (military building to construct, units to train there).
_FACTION_PLAN: dict[str, tuple[str, tuple[str, ...]]] = {
    "AEGIS": ("arsenal", ("guardian", "marksman")),
    "RUST": ("pit", ("ripper", "spitter")),
}


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
        self._military_building, self._army_units = _FACTION_PLAN.get(
            faction_for_team(team), ("arsenal", ("guardian",))
        )

    def step(self) -> None:
        """Advance the AI; issue orders on its decision cadence."""
        self._frame += 1
        if self._frame % self._decision_interval != 0:
            return
        group = self._manager.entities.get(self._team)
        if group is None:
            return
        self._assign_idle_workers(group)
        self._build_military(group)
        self._train_army(group)
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

    def _build_military(self, group: EntitiesGroup) -> None:
        # Arsenal/Pit subclass Barracks, so they live in the ``barracks`` roster.
        if group.barracks or not group.bases or not group.peasents:
            return
        can_construct, _ = self._manager.construction.can_team_construct(self._team, self._military_building)
        if not can_construct:
            return
        base = group.bases[0]
        builder = group.peasents[0]
        for offset_x, offset_y in ((140, 0), (-140, 0), (0, 140), (0, -140)):
            if self._manager.construct_building(
                builder, self._military_building, (base.x + offset_x, base.y + offset_y)
            ):
                return

    def _train_army(self, group: EntitiesGroup) -> None:
        for producer in group.barracks:
            if producer.is_under_construction or len(self._manager.production.queue_for(producer)) >= 2:
                continue
            for unit_type in self._army_units:
                if self._manager.produce_unit(producer, unit_type):
                    break

    def _launch_attack(self, group: EntitiesGroup) -> None:
        army = [*group.knights, *group.archers, *group.mages]
        if len(army) < self.ATTACK_FORCE_SIZE:
            return
        target_base = self._enemy_base()
        if target_base is None:
            return
        idle = [unit for unit in army if unit.state in {"IDLE", "HOLDING"}]
        if idle:
            self._manager.issue_attack_move_order(self._team, target_base.get_center(), idle)

    def _enemy_base(self) -> Base | None:
        for team, other_group in self._manager.entities.items():
            if team == self._team:
                continue
            for base in other_group.bases:
                if base.life > 0:
                    return base
        return None
