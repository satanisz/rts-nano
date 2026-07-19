"""Deterministic simulation tick orchestration without presentation state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.simulation.entities import Peasant
from rts_nano.simulation.entities.base import Building, Resource, Unit
from rts_nano.simulation.events import AttackLanded

if TYPE_CHECKING:
    from rts_nano.game.combat import CombatSystem
    from rts_nano.game.construction import ConstructionSystem
    from rts_nano.game.effects import EffectsSystem
    from rts_nano.game.gather import GatherSystem
    from rts_nano.game.movement import MovementSystem
    from rts_nano.game.production import ProductionSystem
    from rts_nano.game.state import GameState
    from rts_nano.game.victory import VictorySystem
    from rts_nano.simulation.entities.base import Entity


class SimulationRunner:
    """Own system order, tick count, and a bounded output-event queue."""

    def __init__(
        self,
        state: GameState,
        movement: MovementSystem,
        production: ProductionSystem,
        combat: CombatSystem,
        effects: EffectsSystem,
        victory: VictorySystem,
        gather: GatherSystem,
        construction: ConstructionSystem,
    ) -> None:
        """Bind one state to its deterministic gameplay systems."""
        self.state = state
        self.movement = movement
        self.production = production
        self.combat = combat
        self.effects = effects
        self.victory = victory
        self.gather = gather
        self.construction = construction
        self.events: list[AttackLanded] = []

    def step(self) -> set[Entity]:
        """Advance exactly one simulation tick and return removed entities."""
        self.state.tick_count += 1
        self.events.clear()
        self._update_mobile_height_levels()
        all_entities = self.state.all_entities
        collidables = [entity for entity in all_entities if isinstance(entity, (Unit, Building))]
        self.state.spatial_index.rebuild(collidables)

        for entity in all_entities:
            if getattr(entity, "life", 1) <= 0:
                continue
            if isinstance(entity, Unit):
                self._update_unit(entity)
            if isinstance(entity, Peasant):
                self.gather.update_peasant(entity, all_entities)

        self.construction.update()
        self.production.update()
        self.events.extend(self.combat.update())
        self.effects.update()
        removed = self._remove_dead_entities()
        self.victory.update()
        return removed

    def _update_unit(self, entity: Unit) -> None:
        query_radius = self.movement.attack_move_acquire_range(entity) + self.state.spatial_index.max_radius
        query_radius += float(entity.splash_radius)
        nearby = self.state.spatial_index.query(entity.get_center(), query_radius)
        self.movement.update_attack_move_target(entity, nearby)
        entity.update(nearby, self.movement.can_unit_move_to)
        self._clamp_unit_to_world(entity)
        self.movement.update_unit_stuck_recovery(entity)
        attack_event = entity.consume_attack_event()
        if attack_event and entity.entity_id is not None:
            source, target, _, target_entity = attack_event
            self.events.append(AttackLanded(entity.entity_id, entity.content_id, source, target, target_entity))
        self.movement.resume_or_finish_attack_move(entity)
        self.movement.update_patrol(entity)

    def _update_mobile_height_levels(self) -> None:
        for team in self.state.teams:
            for entity in self.state.entities_for_team(team):
                entity.height_level = self.state.terrain.height_at(entity.get_center())

    def _clamp_unit_to_world(self, unit: Unit) -> None:
        radius = unit.radius
        unit.x = min(max(unit.x, radius), self.state.map_width - radius)
        unit.y = min(max(unit.y, radius), self.state.map_height - radius)

    def _remove_dead_entities(self) -> set[Entity]:
        removed = {
            entity for entity in self.state.all_entities if not isinstance(entity, Resource) and entity.life <= 0
        }
        for entity in removed:
            self.state.store.remove(entity)
        return removed
