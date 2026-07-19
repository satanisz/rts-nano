"""Deterministic simulation tick orchestration without presentation state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.simulation.entities import Peasant
from rts_nano.simulation.entities.base import Resource, Unit
from rts_nano.simulation.events import AttackLanded

if TYPE_CHECKING:
    from rts_nano.game.combat import CombatSystem
    from rts_nano.game.construction import ConstructionSystem
    from rts_nano.game.effects import EffectsSystem
    from rts_nano.game.gather import GatherSystem
    from rts_nano.game.movement import MovementSystem
    from rts_nano.game.orders import OrderSystem
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
        orders: OrderSystem,
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
        self.orders = orders
        self.events: list[AttackLanded] = []

    def step(self) -> set[Entity]:
        """Advance exactly one simulation tick and return removed entities."""
        self.state.tick_count += 1
        self.events.clear()
        all_entities = tuple(self.state.store)
        self._update_height_levels(all_entities)
        for entity in all_entities:
            if getattr(entity, "life", 1) <= 0:
                continue
            if isinstance(entity, Unit):
                self._update_unit(entity)
                self.state.spatial_index.update(entity)
            if isinstance(entity, Peasant):
                self.gather.update_peasant(entity, all_entities)

        self.construction.update()
        spawned_units = self.production.update()
        for producer, unit in spawned_units:
            self.orders.apply_producer_rally(producer, unit)
        self.orders.update_queues()
        self.events.extend(self.combat.update())
        self.effects.update()
        removed = self._remove_dead_entities(all_entities)
        self.victory.update()
        return removed

    def _update_unit(self, entity: Unit) -> None:
        self.movement.refresh_path_for_obstacles(entity)
        max_radius = self.state.spatial_index.max_radius
        if entity.attack_move_destination is not None and entity.target_entity is None:
            acquisition_radius = self.movement.attack_move_acquire_range(entity) + max_radius
            acquisition_candidates = self.state.spatial_index.query(entity.get_center(), acquisition_radius)
            self.movement.update_attack_move_target(entity, acquisition_candidates)

        # Collision response needs only the swept local neighborhood, not every
        # entity inside the much larger vision/acquisition square.
        collision_radius = entity.speed + entity.radius + max_radius
        nearby = self.state.spatial_index.query(entity.get_center(), collision_radius)
        if entity.splash_radius > 0 and entity.target_entity is not None:
            splash_candidates = self.state.spatial_index.query(
                entity.target_entity.get_center(), entity.splash_radius + max_radius
            )
            seen = set(nearby)
            nearby.extend(candidate for candidate in splash_candidates if candidate not in seen)
        entity.update(nearby, self.movement.can_unit_move_to)
        self._clamp_unit_to_world(entity)
        self.movement.update_unit_stuck_recovery(entity)
        attack_event = entity.consume_attack_event()
        if attack_event and entity.entity_id is not None:
            source, target, _, target_entity = attack_event
            self.events.append(AttackLanded(entity.entity_id, entity.content_id, source, target, target_entity))
        self.movement.resume_or_finish_attack_move(entity)
        self.movement.update_patrol(entity)

    def _update_height_levels(self, entities: tuple[Entity, ...]) -> None:
        """Update height without allocating one temporary team list per tick."""
        for entity in entities:
            if not isinstance(entity, Resource):
                entity.height_level = self.state.terrain.height_at(entity.get_center())

    def _clamp_unit_to_world(self, unit: Unit) -> None:
        radius = unit.radius
        unit.x = min(max(unit.x, radius), self.state.map_width - radius)
        unit.y = min(max(unit.y, radius), self.state.map_height - radius)

    def _remove_dead_entities(self, entities: tuple[Entity, ...]) -> set[Entity]:
        removed = {entity for entity in entities if not isinstance(entity, Resource) and entity.life <= 0}
        for entity in removed:
            self.state.remove_runtime_entity(entity)
        return removed
