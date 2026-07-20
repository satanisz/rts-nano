"""Deterministic caster energy, cooldown, targeting, and order tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from rts_nano.content import (
    BUILDING_DEFINITIONS,
    FACTION_DEFINITIONS,
    RESOURCE_DEFINITIONS,
    UNIT_DEFINITIONS,
    AbilityDefinition,
    ContentRegistry,
    ResourceCost,
    UpgradeDefinition,
)
from rts_nano.game.abilities import AbilitySystem
from rts_nano.game.orders import OrderSystem
from rts_nano.game.types import (
    AbilityEffectKind,
    AbilityId,
    AbilityTargetKind,
    ContentId,
    FactionId,
    UpgradeId,
)
from rts_nano.game.upgrades import UpgradeSystem
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import Arclight, Knight, Mage, TeamColor


def _content() -> tuple[ContentRegistry, AbilityDefinition]:
    ability = AbilityDefinition(
        id=AbilityId("arc_bolt"),
        display_name="Arc Bolt",
        description="Test-only deterministic enemy cast.",
        target_kind=AbilityTargetKind.ENEMY,
        effect_kind=AbilityEffectKind.DIRECT_DAMAGE,
        energy_cost=20,
        cooldown_frames=6,
        cast_range=180,
        magnitude=11,
    )
    upgrade = UpgradeDefinition(
        id=UpgradeId("arc_training"),
        display_name="Arc Training",
        description="Unlock Arc Bolt.",
        faction=FactionId("AEGIS"),
        research_at=(ContentId("spire"),),
        cost=ResourceCost(wood=10, gold=10),
        research_frames=5,
        affected_content=(ContentId("mage"),),
        granted_abilities=(ability.id,),
    )
    registry = ContentRegistry(
        units=UNIT_DEFINITIONS,
        buildings=BUILDING_DEFINITIONS,
        resources=RESOURCE_DEFINITIONS,
        factions=FACTION_DEFINITIONS,
        upgrades=(upgrade,),
        abilities=(ability,),
    )
    return registry, ability


def _systems() -> tuple[HeadlessSimulation, AbilitySystem, OrderSystem, Mage, Knight, AbilityDefinition]:
    registry, ability = _content()
    simulation = HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[100, 100]], "mage": [[250, 250]]},
            "Red": {"faction_id": "RUST", "base": [[700, 500]], "knight": [[350, 250]]},
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
    manager = simulation.manager
    assert UpgradeSystem(manager.state, registry).complete(TeamColor.BLUE, "arc_training")
    abilities = AbilitySystem(manager.state, manager.movement, registry)
    orders = OrderSystem(manager.state, manager.movement, manager.production, manager.construction, abilities)
    mage = manager.state.entities_by_content_id("mage", team=TeamColor.BLUE)[0]
    knight = manager.state.entities_by_content_id("knight", team=TeamColor.RED)[0]
    assert isinstance(mage, Mage)
    assert isinstance(knight, Knight)
    return simulation, abilities, orders, mage, knight, ability


def test_successful_cast_pays_on_effect_and_starts_cooldown() -> None:
    """Issue is free; confirmed effect atomically spends energy and starts cooldown."""
    simulation, abilities, orders, mage, knight, ability = _systems()
    initial_energy = mage.energy
    initial_life = knight.life

    assert orders.issue_cast_order(TeamColor.BLUE, str(ability.id), mage, target=knight) == 1
    assert mage.energy == initial_energy
    assert abilities.update_cast(mage)

    assert knight.life == initial_life - ability.magnitude
    assert mage.energy == initial_energy - ability.energy_cost
    assert mage.ability_cooldowns[str(ability.id)] == ability.cooldown_frames
    assert mage.current_order is None
    simulation.close()


def test_cast_can_be_shift_queued_and_normal_command_interrupts_for_free() -> None:
    """Queued casts wait for active movement; replacement commands never charge them."""
    simulation, abilities, orders, mage, knight, ability = _systems()
    initial_energy = mage.energy
    assert orders.issue_move_order(TeamColor.BLUE, (200, 250), [mage]) == 1
    assert orders.issue_cast_order(TeamColor.BLUE, str(ability.id), mage, target=knight, queue=True) == 1
    assert mage.order_queue[0].kind == "cast"

    mage.state = "IDLE"
    orders.update_queues()
    assert mage.current_order is not None
    assert mage.current_order.kind == "cast"
    assert orders.issue_move_order(TeamColor.BLUE, (100, 250), [mage]) == 1
    assert mage.current_order is not None
    assert mage.current_order.kind == "move"
    assert mage.energy == initial_energy
    assert not mage.ability_cooldowns
    assert not abilities.update_cast(mage)
    simulation.close()


def test_dead_target_skips_cast_without_energy_or_cooldown() -> None:
    """A target lost after issue invalidates cleanly at effect time."""
    simulation, abilities, orders, mage, knight, ability = _systems()
    initial_energy = mage.energy
    assert orders.issue_cast_order(TeamColor.BLUE, str(ability.id), mage, target=knight) == 1
    knight.life = 0

    assert not abilities.update_cast(mage)
    assert mage.energy == initial_energy
    assert not mage.ability_cooldowns
    assert mage.current_order is None
    simulation.close()


def test_insufficient_energy_waits_and_regenerates_in_integer_frames() -> None:
    """A valid order waits at zero energy until deterministic local regeneration permits it."""
    simulation, abilities, orders, mage, knight, ability = _systems()
    mage.energy = ability.energy_cost - 1
    assert orders.issue_cast_order(TeamColor.BLUE, str(ability.id), mage, target=knight) == 1
    assert not abilities.update_cast(mage)
    assert mage.current_order is not None

    for _ in range(mage.energy_regen_denominator):
        mage.update(())
    assert mage.energy == ability.energy_cost
    assert abilities.update_cast(mage)
    assert mage.energy == 0
    simulation.close()


def test_arclight_has_no_caster_state_and_registry_rejects_invalid_ability() -> None:
    """Artillery remains separate and malformed ability values fail at startup."""
    arclight = Arclight(0, 0, TeamColor.BLUE)
    assert not hasattr(arclight, "energy")
    registry, ability = _content()
    assert registry.get_ability("arc_bolt") is ability

    with pytest.raises(ValueError, match="negative values"):
        ContentRegistry(
            units=UNIT_DEFINITIONS,
            buildings=BUILDING_DEFINITIONS,
            resources=RESOURCE_DEFINITIONS,
            factions=FACTION_DEFINITIONS,
            abilities=(replace(ability, energy_cost=-1),),
        )
