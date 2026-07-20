"""Deterministic team-wide upgrade derivation and entity transitions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.content import CONTENT, ContentRegistry
from rts_nano.game.types import ModifierStat, UpgradeId
from rts_nano.simulation.entities.base import Building, Unit

if TYPE_CHECKING:
    from rts_nano.content import BuildingDefinition, UnitDefinition, UpgradeDefinition
    from rts_nano.game.state import GameState, TeamState
    from rts_nano.simulation.entities.base import Entity, TeamColor

type NumericStat = int | float


class UpgradeSystem:
    """Apply canonical definitions only when research completes or an entity spawns."""

    def __init__(self, state: GameState, registry: ContentRegistry = CONTENT) -> None:
        """Bind one game state to an immutable content registry."""
        self._state = state
        self._registry = registry

    def can_complete(self, team: TeamColor, upgrade_id: str) -> tuple[bool, str | None]:
        """Validate faction, prerequisites, conflicts, and exclusivity."""
        team_state = self._state.team(team)
        if team_state is None:
            return False, "missing_team"
        try:
            upgrade = self._registry.get_upgrade(upgrade_id)
        except ValueError:
            return False, "unsupported_upgrade"
        if upgrade.faction != team_state.faction_id:
            return False, "wrong_faction"
        if team_state.has_upgrade(upgrade_id):
            return False, "already_completed"
        if any(not team_state.has_upgrade(str(item)) for item in upgrade.required_upgrades):
            return False, "missing_upgrade"
        if any(team_state.has_upgrade(str(item)) for item in upgrade.conflicts):
            return False, "conflicting_upgrade"
        if upgrade.exclusive_group is not None:
            for completed_id in team_state.completed_upgrades:
                completed = self._registry.get_upgrade(str(completed_id))
                if completed.exclusive_group == upgrade.exclusive_group:
                    return False, "exclusive_choice_completed"
        return True, None

    def complete(self, team: TeamColor, upgrade_id: str) -> bool:
        """Complete an upgrade and recompute affected entities once in stable order."""
        can_complete, _ = self.can_complete(team, upgrade_id)
        if not can_complete:
            return False
        team_state = self._state.teams[team]
        team_state.complete_upgrade(UpgradeId(upgrade_id))
        affected = {str(content_id) for content_id in self._registry.get_upgrade(upgrade_id).affected_content}
        entities = sorted(
            (
                entity
                for entity in self._state.entities_for_team(team)
                if str(entity.content_id) in affected and entity.entity_id is not None
            ),
            key=lambda entity: int(entity.entity_id),
        )
        for entity in entities:
            self.apply_to_entity(entity, team_state)
        return True

    def apply_to_entity(self, entity: Entity, team_state: TeamState | None = None) -> None:
        """Recompute one existing or newly spawned entity from immutable base stats."""
        if not isinstance(entity, (Unit, Building)):
            return
        if team_state is None:
            team_state = self._state.team(entity.team)
        if team_state is None:
            return
        stats = self.effective_stats(entity.definition, team_state.completed_upgrades)
        entity.active_behaviors = frozenset(
            sorted(
                behavior
                for upgrade_id in team_state.completed_upgrades
                for upgrade in (self._registry.get_upgrade(str(upgrade_id)),)
                if entity.definition.id in upgrade.affected_content
                for behavior in upgrade.granted_behaviors
            )
        )
        old_max_life = entity.max_life
        entity.max_life = int(stats[ModifierStat.MAX_LIFE])
        entity.life = min(entity.max_life, max(0, entity.life + entity.max_life - old_max_life))
        old_shield_max = entity.shield_max
        entity.shield_max = int(stats[ModifierStat.SHIELD_MAX])
        entity.shield = min(entity.shield_max, max(0, entity.shield + entity.shield_max - old_shield_max))
        for stat, value in stats.items():
            attribute = stat.value
            if attribute in {"max_life", "shield_max"} or not hasattr(entity, attribute):
                continue
            setattr(entity, attribute, value)
        if isinstance(entity, Unit):
            base_speed = float(stats[ModifierStat.SPEED])
            if entity.slow_remaining_frames > 0:
                entity.slow_restore_speed = base_speed
                entity.speed = base_speed * getattr(entity, "slow_multiplier", 1.0)
            else:
                entity.speed = base_speed

    def effective_stats(
        self,
        definition: UnitDefinition | BuildingDefinition,
        completed_ids: list[UpgradeId],
    ) -> dict[ModifierStat, NumericStat]:
        """Derive supported effective stats in canonical upgrade-ID order."""
        stats = {stat: getattr(definition, stat.value) for stat in ModifierStat if hasattr(definition, stat.value)}
        for upgrade_id in sorted(completed_ids, key=str):
            upgrade = self._registry.get_upgrade(str(upgrade_id))
            if definition.id not in upgrade.affected_content:
                continue
            self._apply_modifiers(stats, upgrade)
        return stats

    @staticmethod
    def _apply_modifiers(stats: dict[ModifierStat, NumericStat], upgrade: UpgradeDefinition) -> None:
        for modifier in upgrade.modifiers:
            current = stats[modifier.stat]
            multiplied = current * modifier.numerator / modifier.denominator
            value = multiplied + modifier.add
            stats[modifier.stat] = value if isinstance(current, float) else int(value)
