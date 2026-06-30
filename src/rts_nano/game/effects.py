"""Per-frame status effects: AEGIS shield regen (and, later, RUST poison).

This system owns the once-per-frame tick for time-based combat effects so they
live in one deterministic place rather than being scattered across unit/tower
update paths. Damage application (draining shields before life) happens in
``rules.apply_damage`` at the moment of the hit; this system only advances the
effects that change between hits, such as regenerating an out-of-combat shield.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.constants import FPS, POISON_INTERVAL
from rts_nano.game.rules import apply_damage

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Entity
    from rts_nano.game.state import GameState


class EffectsSystem:
    """Advance regenerating/decaying status effects once per simulation frame."""

    def __init__(self, state: GameState) -> None:
        """Initialize the effects system for one game state."""
        self._state = state

    def update(self) -> None:
        """Tick every living entity's status effects for one frame."""
        for entity in self._state.all_entities:
            if entity.life <= 0:
                continue
            self._tick_poison(entity)
            self._regen_shield(entity)

    @staticmethod
    def _tick_poison(entity: Entity) -> None:
        """Advance an active poison stack, dealing damage on its interval cadence."""
        if entity.poison_remaining_frames <= 0:
            return
        entity.poison_remaining_frames -= 1
        entity.poison_interval_counter += 1
        if entity.poison_interval_counter >= POISON_INTERVAL:
            entity.poison_interval_counter = 0
            # Route through apply_damage so poison also chips AEGIS shields and
            # keeps shielded targets out of regen while the toxin lingers.
            apply_damage(entity, entity.poison_tick_damage)
        if entity.poison_remaining_frames <= 0:
            entity.poison_tick_damage = 0
            entity.poison_interval_counter = 0

    @staticmethod
    def _regen_shield(entity: Entity) -> None:
        """Recover shield once a shielded entity has been out of combat long enough."""
        if entity.shield_max <= 0:
            return
        if entity.frames_since_damaged < entity.shield_regen_delay:
            entity.frames_since_damaged += 1
            return
        if entity.shield >= entity.shield_max:
            return
        entity.shield_regen_accumulator += entity.shield_regen / FPS
        whole = int(entity.shield_regen_accumulator)
        if whole > 0:
            entity.shield_regen_accumulator -= whole
            entity.shield = min(entity.shield_max, entity.shield + whole)
