"""AEGIS doctrine choices, behaviors, and caster effects."""

from __future__ import annotations

import pytest

from rts_nano.game.entity_factory import EntityFactory
from rts_nano.game.rules import combat_attack_bonus, combat_shield_modifier
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import Archer, Guardian, Knight, Mage, TeamColor
from rts_nano.simulation.entities.base import Building, Unit


def _simulation() -> HeadlessSimulation:
    simulation = HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {
                "faction_id": "AEGIS",
                "base": [[100, 100]],
                "arsenal": [[180, 100]],
                "spire": [[260, 100]],
                "knight": [[250, 300]],
                "archer": [[200, 300]],
                "mage": [[300, 300]],
                "guardian": [[350, 300]],
                "arclight": [[150, 300]],
            },
            "Red": {
                "faction_id": "RUST",
                "base": [[700, 500]],
                "knight": [[400, 300]],
            },
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
    simulation.manager.teams[TeamColor.BLUE].resources.update({"wood": 10000, "gold": 10000})
    return simulation


def _entity[T: Unit | Building](simulation: HeadlessSimulation, content_id: str, team: TeamColor, kind: type[T]) -> T:
    entity = simulation.manager.state.entities_by_content_id(content_id, team=team)[0]
    assert isinstance(entity, kind)
    return entity


@pytest.mark.parametrize(
    ("producer_id", "first", "second"),
    [
        ("arsenal", "aegis_knight_bulwark", "aegis_knight_vanguard"),
        ("arsenal", "aegis_archer_longshot", "aegis_archer_arcshot"),
        ("spire", "aegis_mage_shieldweaver", "aegis_mage_arcbinder"),
    ],
)
def test_aegis_doctrine_groups_reserve_and_complete_exclusively(
    producer_id: str,
    first: str,
    second: str,
) -> None:
    """Each AEGIS archetype choice is atomic while queued and permanent after completion."""
    simulation = _simulation()
    manager = simulation.manager
    producer = _entity(simulation, producer_id, TeamColor.BLUE, Building)
    assert manager.research_upgrade(producer, first)
    assert manager.can_research(producer, second) == (False, "exclusive_choice_reserved")
    assert manager.cancel_production(producer)
    assert manager.research_upgrade(producer, second)
    frames = manager.production.queue_for(producer)[0].total_frames
    simulation.step(frames)
    assert manager.teams[TeamColor.BLUE].has_upgrade(second)
    assert manager.can_research(producer, first) == (False, "exclusive_choice_completed")
    simulation.close()


def test_bulwark_hold_and_vanguard_charge_are_distinct() -> None:
    """Bulwark protects a held line; Vanguard converts movement into one bounded impact."""
    bulwark_sim = _simulation()
    bulwark = _entity(bulwark_sim, "knight", TeamColor.BLUE, Knight)
    assert bulwark_sim.manager.upgrades.complete(TeamColor.BLUE, "aegis_knight_bulwark")
    base_modifier = bulwark.shield_modifier
    bulwark.state = "HOLDING"
    assert bulwark.shield_max == 40
    assert combat_shield_modifier(bulwark) == base_modifier + 2
    bulwark_sim.close()

    vanguard_sim = _simulation()
    vanguard = _entity(vanguard_sim, "knight", TeamColor.BLUE, Knight)
    enemy = _entity(vanguard_sim, "knight", TeamColor.RED, Knight)
    assert vanguard_sim.manager.upgrades.complete(TeamColor.BLUE, "aegis_knight_vanguard")
    vanguard.charge_distance = 120
    enemy.x = vanguard.x + 10
    life_before = enemy.life
    assert vanguard._attack(enemy) > 0
    assert enemy.life <= life_before - vanguard.attack_damage - 6
    assert enemy.stun_remaining_frames == 24
    assert vanguard.charge_distance == 0
    vanguard_sim.close()


def test_longshot_dead_zone_and_arcshot_mark_have_real_tradeoff() -> None:
    """Longshot changes setup ranges; Arcshot instead enables bounded team focus fire."""
    longshot_sim = _simulation()
    archer = _entity(longshot_sim, "archer", TeamColor.BLUE, Archer)
    base_range = archer.ranged_attack_range
    base_dead_zone = archer.ranged_min_attack_range
    assert longshot_sim.manager.upgrades.complete(TeamColor.BLUE, "aegis_archer_longshot")
    assert archer.ranged_attack_range == base_range + 60
    assert archer.ranged_min_attack_range == base_dead_zone + 20
    longshot_sim.close()

    arcshot_sim = _simulation()
    archer = _entity(arcshot_sim, "archer", TeamColor.BLUE, Archer)
    enemy = _entity(arcshot_sim, "knight", TeamColor.RED, Knight)
    assert arcshot_sim.manager.upgrades.complete(TeamColor.BLUE, "aegis_archer_arcshot")
    enemy.x = archer.x + 140
    assert archer._attack(enemy) > 0
    assert enemy.arc_mark_remaining_frames == 90
    assert combat_attack_bonus(archer, enemy) == 2
    assert arcshot_sim.manager.upgrades.complete(TeamColor.BLUE, "aegis_arc_targeting")
    arclight = arcshot_sim.manager.state.entities_by_content_id("arclight", team=TeamColor.BLUE)[0]
    assert combat_attack_bonus(arclight, enemy) == 4
    arcshot_sim.step(90)
    assert enemy.arc_mark_remaining_frames == 0
    assert enemy.arc_mark_team is None
    arcshot_sim.close()


def test_barrier_pulse_uses_stable_six_target_cap() -> None:
    """Shield restoration uses the spatial index and stable entity ordering."""
    simulation = _simulation()
    manager = simulation.manager
    mage = _entity(simulation, "mage", TeamColor.BLUE, Mage)
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_mage_shieldweaver")
    guardians = [
        entity
        for entity in manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)
        if isinstance(entity, Guardian)
    ]
    for guardian in guardians:
        guardian.shield = 0
    for index in range(7):
        guardian = EntityFactory.create("guardian", 280 + index * 5, 320, TeamColor.BLUE)
        assert isinstance(guardian, Guardian)
        manager.state.add_runtime_entity(guardian)
        guardian.shield = 0
        guardians.append(guardian)
    mage.shield = 0

    assert (
        manager.issue_cast_order(
            TeamColor.BLUE,
            "barrier_pulse",
            mage,
            destination=(300, 320),
        )
        == 1
    )
    simulation.step()

    restored = [entity for entity in [mage, *guardians] if entity.shield > 0]
    assert len(restored) == 6
    assert [int(entity.entity_id or 0) for entity in restored] == sorted(
        int(entity.entity_id or 0) for entity in restored
    )
    simulation.close()


def test_arc_bind_slow_and_mark_expire_and_restore_speed() -> None:
    """Arc Bind pays once, marks/slows one enemy, and restores canonical movement on expiry."""
    simulation = _simulation()
    manager = simulation.manager
    mage = _entity(simulation, "mage", TeamColor.BLUE, Mage)
    enemy = _entity(simulation, "knight", TeamColor.RED, Knight)
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_mage_arcbinder")
    base_speed = enemy.speed
    enemy.x = mage.x + 100

    assert manager.issue_cast_order(TeamColor.BLUE, "arc_bind", mage, target=enemy) == 1
    simulation.step()
    assert enemy.speed < base_speed
    assert enemy.arc_mark_team == TeamColor.BLUE
    assert enemy.slow_remaining_frames == 119

    simulation.step(119)
    assert enemy.speed == base_speed
    assert enemy.arc_mark_remaining_frames == 0
    assert enemy.arc_mark_team is None
    simulation.close()
