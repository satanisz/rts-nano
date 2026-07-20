"""Deterministic registry-backed team upgrade behavior."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rts_nano.content import (
    BUILDING_DEFINITIONS,
    FACTION_DEFINITIONS,
    RESOURCE_DEFINITIONS,
    UNIT_DEFINITIONS,
    ContentRegistry,
    ResourceCost,
    StatModifier,
    UpgradeDefinition,
)
from rts_nano.game.types import ContentId, ExclusivityGroupId, FactionId, ModifierStat, UpgradeId
from rts_nano.game.upgrades import UpgradeSystem
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import Knight, TeamColor


def _upgrade(
    upgrade_id: str,
    *modifiers: StatModifier,
    exclusive_group: str | None = None,
    required_upgrades: tuple[UpgradeId, ...] = (),
) -> UpgradeDefinition:
    return UpgradeDefinition(
        id=UpgradeId(upgrade_id),
        display_name=upgrade_id.replace("_", " ").title(),
        description="Test-only deterministic upgrade.",
        faction=FactionId("AEGIS"),
        research_at=(ContentId("arsenal"),),
        cost=ResourceCost(wood=50, gold=25),
        research_frames=60,
        required_upgrades=required_upgrades,
        exclusive_group=ExclusivityGroupId(exclusive_group) if exclusive_group else None,
        affected_content=(ContentId("knight"),),
        modifiers=modifiers,
    )


def _registry(*upgrades: UpgradeDefinition) -> ContentRegistry:
    return ContentRegistry(
        units=UNIT_DEFINITIONS,
        buildings=BUILDING_DEFINITIONS,
        resources=RESOURCE_DEFINITIONS,
        factions=FACTION_DEFINITIONS,
        upgrades=upgrades,
    )


def _simulation() -> HeadlessSimulation:
    return HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[100, 100]], "knight": [[180, 100]]},
            "Red": {"faction_id": "RUST", "base": [[700, 500]]},
            "Resources": {"wood": [], "gold": []},
            "Terrain": {
                "width": 800,
                "height": 600,
                "high_ground": [],
                "water": [],
                "ramps": [],
                "rocks": [],
                "grass": [],
            },
        }
    )


def test_upgrade_recomputes_from_base_in_canonical_id_order() -> None:
    """Completion order cannot compound or reorder immutable modifiers."""
    add = _upgrade("z_add", StatModifier(ModifierStat.ATTACK_DAMAGE, add=3))
    double = _upgrade("a_double", StatModifier(ModifierStat.ATTACK_DAMAGE, numerator=2))
    registry = _registry(add, double)
    simulation = _simulation()
    system = UpgradeSystem(simulation.manager.state, registry)
    knight = simulation.manager.state.entities_by_content_id("knight", team=TeamColor.BLUE)[0]
    assert isinstance(knight, Knight)
    base_damage = knight.definition.attack_damage

    assert system.complete(TeamColor.BLUE, "z_add")
    assert knight.attack_damage == base_damage + 3
    assert system.complete(TeamColor.BLUE, "a_double")
    assert knight.attack_damage == base_damage * 2 + 3
    assert not system.complete(TeamColor.BLUE, "z_add")
    assert knight.attack_damage == base_damage * 2 + 3
    assert [str(item) for item in simulation.manager.teams[TeamColor.BLUE].completed_upgrades] == [
        "a_double",
        "z_add",
    ]

    future = Knight(240, 100, TeamColor.BLUE)
    system.apply_to_entity(future)
    assert future.attack_damage == knight.attack_damage
    simulation.close()


def test_capacity_upgrade_preserves_damage_depletion_and_cooldown() -> None:
    """Capacity deltas add room without healing damage or resetting attacks."""
    durable = _upgrade(
        "durable",
        StatModifier(ModifierStat.MAX_LIFE, add=20),
        StatModifier(ModifierStat.SHIELD_MAX, add=15),
    )
    simulation = _simulation()
    system = UpgradeSystem(simulation.manager.state, _registry(durable))
    knight = simulation.manager.state.entities_by_content_id("knight", team=TeamColor.BLUE)[0]
    assert isinstance(knight, Knight)
    knight.life -= 40
    knight.attack_cooldown = 17

    assert system.complete(TeamColor.BLUE, "durable")
    assert (knight.max_life, knight.life) == (120, 80)
    assert (knight.shield_max, knight.shield) == (15, 15)
    assert knight.attack_cooldown == 17
    simulation.close()


def test_exclusive_upgrade_choice_is_team_wide() -> None:
    """A completed choice blocks its sibling and the wrong faction."""
    first = _upgrade("bulwark", exclusive_group="aegis_knight")
    second = _upgrade("vanguard", exclusive_group="aegis_knight")
    simulation = _simulation()
    system = UpgradeSystem(simulation.manager.state, _registry(first, second))

    assert system.can_complete(TeamColor.RED, "bulwark") == (False, "wrong_faction")
    assert system.complete(TeamColor.BLUE, "bulwark")
    assert system.can_complete(TeamColor.BLUE, "vanguard") == (False, "exclusive_choice_completed")
    simulation.close()


def test_registry_rejects_invalid_upgrade_cycles_and_modifiers() -> None:
    """Malformed research graphs fail before a simulation starts."""
    first = _upgrade("first", required_upgrades=(UpgradeId("second"),))
    second = _upgrade("second", required_upgrades=(UpgradeId("first"),))
    with pytest.raises(ValueError, match="cycle"):
        _registry(first, second)

    invalid = replace(
        _upgrade("invalid"),
        modifiers=(StatModifier(ModifierStat.ATTACK_DAMAGE, denominator=0),),
    )
    with pytest.raises(ValueError, match="invalid modifier"):
        _registry(invalid)
