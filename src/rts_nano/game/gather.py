"""Resource harvesting tick extracted from ``GameManager``.

The system advances one peasant's harvesting state each frame: it decrements the
targeted resource, accumulates cargo, finds a replacement node when one depletes,
and routes the worker between resource and base. Resource lists and team banks
come from the shared ``GameState``; path assignment is delegated to the
``MovementSystem``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.constants import HARVEST_SEARCH_RADIUS
from rts_nano.game.rules import find_replacement_resource, nearest_entity
from rts_nano.simulation.entities import Gold, Wood

if TYPE_CHECKING:
    from collections.abc import Iterable

    from rts_nano.game.movement import MovementSystem
    from rts_nano.game.state import GameState
    from rts_nano.simulation.entities.base import Entity
    from rts_nano.simulation.entities.units import Peasant


class GatherSystem:
    """Advance peasant harvesting and depositing over the game state."""

    def __init__(self, state: GameState, movement: MovementSystem) -> None:
        """Initialize the gather system for one game state."""
        self._state = state
        self._movement = movement

    def update_peasant(self, peasant: Peasant, all_entities: Iterable[Entity]) -> None:
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
        self._state.remove_runtime_entity(resource)
        resource_list = self._state.resources_by_content("wood" if is_wood else "gold")
        new_resource = find_replacement_resource(resource, resource_list, search_radius=HARVEST_SEARCH_RADIUS)
        peasant.source_resource = new_resource
        peasant.target_entity = new_resource

    def _send_to_base(self, peasant: Peasant, *, is_wood: bool) -> None:
        if is_wood and peasant.carry_wood > peasant.max_carry:
            peasant.carry_wood = peasant.max_carry
        elif not is_wood and peasant.carry_gold > peasant.max_carry:
            peasant.carry_gold = peasant.max_carry

        team_bases = self._state.entities_by_content_id("base", team=peasant.team)
        nearest_base = nearest_entity(peasant, team_bases)
        if nearest_base:
            self._movement.assign_unit_target(peasant, nearest_base.get_center(), nearest_base)
        else:
            peasant.state = "IDLE"

    def _update_depositing(self, peasant: Peasant, all_entities: Iterable[Entity]) -> None:
        team_state = self._state.team(peasant.team)
        if team_state:
            team_state.resources["wood"] += peasant.carry_wood
            team_state.resources["gold"] += peasant.carry_gold
        peasant.carry_wood = 0
        peasant.carry_gold = 0

        source = peasant.source_resource
        if source is not None and source in all_entities and source.amount > 0:
            self._movement.assign_unit_target(peasant, source.get_center(), source)
        else:
            peasant.state = "IDLE"
            peasant.source_resource = None
