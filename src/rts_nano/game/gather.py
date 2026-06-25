"""Resource harvesting tick extracted from ``GameManager``.

The system advances one peasant's harvesting state each frame: it decrements the
targeted resource, accumulates cargo, finds a replacement node when one depletes,
and routes the worker between resource and base. Cross-entity state (resource
lists, team banks, path assignment) is reached through the manager, matching the
``ProductionSystem``/``ConstructionSystem`` pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities import Gold, Wood
from rts_nano.game.constants import HARVEST_SEARCH_RADIUS
from rts_nano.game.rules import find_replacement_resource, nearest_entity

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Entity
    from rts_nano.game.assets.entities.units import Peasant
    from rts_nano.game.manager import GameManager


class GatherSystem:
    """Advance peasant harvesting and depositing for one manager."""

    def __init__(self, manager: GameManager) -> None:
        """Initialize the gather system for one game manager."""
        self._manager = manager

    def update_peasant(self, peasant: Peasant, all_entities: list[Entity]) -> None:
        """Advance a single peasant's gather/deposit behavior for one frame."""
        if peasant.state == "GATHERING":
            self._update_gathering(peasant)
        elif peasant.state == "DEPOSITING":
            self._update_depositing(peasant, all_entities)

    def _update_gathering(self, peasant: Peasant) -> None:
        resource = peasant.target_entity or peasant.source_resource
        if not isinstance(resource, (Wood, Gold)):
            return
        is_wood = isinstance(resource, Wood)

        if resource.amount > 0:
            gathered = min(1, resource.amount)
            resource.amount -= gathered
            if is_wood:
                peasant.carry_wood += gathered
            else:
                peasant.carry_gold += gathered

            if resource.amount <= 0:
                self._replace_depleted_resource(peasant, resource, is_wood=is_wood)

        carry_amount = peasant.carry_wood if is_wood else peasant.carry_gold
        if carry_amount >= peasant.max_carry or resource.amount <= 0:
            self._send_to_base(peasant, is_wood=is_wood)

    def _replace_depleted_resource(self, peasant: Peasant, resource: Wood | Gold, *, is_wood: bool) -> None:
        if isinstance(resource, Wood) and resource in self._manager.resources.woods:
            self._manager.resources.woods.remove(resource)
        elif isinstance(resource, Gold) and resource in self._manager.resources.golds:
            self._manager.resources.golds.remove(resource)

        resource_list = self._manager.resources.woods if is_wood else self._manager.resources.golds
        new_resource = find_replacement_resource(resource, resource_list, search_radius=HARVEST_SEARCH_RADIUS)
        peasant.source_resource = new_resource
        peasant.target_entity = new_resource

    def _send_to_base(self, peasant: Peasant, *, is_wood: bool) -> None:
        if is_wood and peasant.carry_wood > peasant.max_carry:
            peasant.carry_wood = peasant.max_carry
        elif not is_wood and peasant.carry_gold > peasant.max_carry:
            peasant.carry_gold = peasant.max_carry

        team_group = self._manager.entities.get(peasant.team)
        team_bases = team_group.bases if team_group else []
        nearest_base = nearest_entity(peasant, team_bases)
        if nearest_base:
            self._manager._assign_unit_target(peasant, nearest_base.get_center(), nearest_base)
        else:
            peasant.state = "IDLE"

    def _update_depositing(self, peasant: Peasant, all_entities: list[Entity]) -> None:
        team_group = self._manager.entities.get(peasant.team)
        if team_group:
            team_group.resources["wood"] += peasant.carry_wood
            team_group.resources["gold"] += peasant.carry_gold
        peasant.carry_wood = 0
        peasant.carry_gold = 0

        source = peasant.source_resource
        if source is not None and source in all_entities and source.amount > 0:
            self._manager._assign_unit_target(peasant, source.get_center(), source)
        else:
            peasant.state = "IDLE"
            peasant.source_resource = None
