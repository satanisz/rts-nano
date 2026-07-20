"""RUST doctrine choices, local pack context, poison, and mutation casts."""

from __future__ import annotations

import pytest

from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import Archer, Knight, Mage, TeamColor
from rts_nano.simulation.entities.base import Building


def _simulation() -> HeadlessSimulation:
    simulation = HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {
                "faction_id": "AEGIS",
                "base": [[100, 100]],
                "knight": [[360, 300], [380, 300]],
            },
            "Red": {
                "faction_id": "RUST",
                "base": [[700, 500]],
                "pit": [[650, 500]],
                "chem_vat": [[600, 500]],
                "knight": [[300, 300], [310, 320], [290, 320], [300, 340], [315, 340], [500, 300]],
                "archer": [[280, 260]],
                "mage": [[260, 300]],
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
    simulation.manager.teams[TeamColor.RED].resources.update({"wood": 10000, "gold": 10000})
    return simulation


@pytest.mark.parametrize(
    ("producer_id", "first", "second"),
    [
        ("pit", "rust_knight_frenzy", "rust_knight_pack"),
        ("pit", "rust_archer_venom", "rust_archer_skirmisher"),
        ("chem_vat", "rust_mage_plaguecaller", "rust_mage_mutagenist"),
    ],
)
def test_rust_doctrine_groups_are_exclusive(producer_id: str, first: str, second: str) -> None:
    simulation = _simulation()
    producer = simulation.manager.state.entities_by_content_id(producer_id, team=TeamColor.RED)[0]
    assert isinstance(producer, Building)
    assert simulation.manager.research_upgrade(producer, first)
    assert simulation.manager.can_research(producer, second) == (False, "exclusive_choice_reserved")
    simulation.close()


def test_frenzy_threshold_and_pack_contributor_cap_are_bounded() -> None:
    frenzy_sim = _simulation()
    frenzy = frenzy_sim.manager.state.entities_by_content_id("knight", team=TeamColor.RED)[0]
    assert isinstance(frenzy, Knight)
    assert frenzy_sim.manager.upgrades.complete(TeamColor.RED, "rust_knight_frenzy")
    normal = frenzy._attack_cooldown_frames()
    frenzy.life = frenzy.max_life // 2
    assert frenzy._attack_cooldown_frames() < normal
    frenzy_sim.close()

    pack_sim = _simulation()
    pack = pack_sim.manager.state.entities_by_content_id("knight", team=TeamColor.RED)[0]
    assert isinstance(pack, Knight)
    assert pack_sim.manager.upgrades.complete(TeamColor.RED, "rust_knight_pack")
    pack_sim.step(1)
    assert pack.pack_contributors == 4
    assert pack_sim.manager.upgrades.complete(TeamColor.RED, "rust_advanced_mutations")
    assert pack.active_behaviors == frozenset({"advanced_mutations", "rust_pack"})
    pack_sim.close()


def test_venom_refreshes_and_skirmisher_changes_mobility_not_poison() -> None:
    venom_sim = _simulation()
    archer = venom_sim.manager.state.entities_by_content_id("archer", team=TeamColor.RED)[0]
    target = venom_sim.manager.state.entities_by_content_id("knight", team=TeamColor.BLUE)[0]
    assert isinstance(archer, Archer)
    assert isinstance(target, Knight)
    assert venom_sim.manager.upgrades.complete(TeamColor.RED, "rust_archer_venom")
    archer.x, archer.y = target.x - 180, target.y
    archer._attack(target)
    assert target.poison_tick_damage == 2
    target.poison_remaining_frames = 1
    archer.attack_cooldown = 0
    archer._attack(target)
    assert target.poison_remaining_frames == 90
    venom_sim.close()

    skirmish_sim = _simulation()
    skirmisher = skirmish_sim.manager.state.entities_by_content_id("archer", team=TeamColor.RED)[0]
    assert isinstance(skirmisher, Archer)
    base_speed, base_dead_zone = skirmisher.speed, skirmisher.ranged_min_attack_range
    assert skirmish_sim.manager.upgrades.complete(TeamColor.RED, "rust_archer_skirmisher")
    assert skirmisher.speed > base_speed
    assert skirmisher.ranged_min_attack_range < base_dead_zone
    assert skirmisher.poison_damage == 0
    skirmish_sim.close()


def test_toxic_cloud_and_mutagenic_surge_use_stable_caps() -> None:
    plague_sim = _simulation()
    manager = plague_sim.manager
    mage = manager.state.entities_by_content_id("mage", team=TeamColor.RED)[0]
    enemies = manager.state.entities_by_content_id("knight", team=TeamColor.BLUE)
    assert isinstance(mage, Mage)
    assert manager.upgrades.complete(TeamColor.RED, "rust_mage_plaguecaller")
    assert manager.issue_cast_order(TeamColor.RED, "toxic_cloud", mage, destination=(370, 300)) == 1
    plague_sim.step(1)
    assert all(enemy.poison_tick_damage == 3 for enemy in enemies)
    assert mage.energy == 60
    plague_sim.close()

    surge_sim = _simulation()
    manager = surge_sim.manager
    mage = manager.state.entities_by_content_id("mage", team=TeamColor.RED)[0]
    allies = manager.state.entities_by_content_id("knight", team=TeamColor.RED)
    assert isinstance(mage, Mage)
    assert manager.upgrades.complete(TeamColor.RED, "rust_mage_mutagenist")
    assert manager.issue_cast_order(TeamColor.RED, "mutagenic_surge", mage, destination=(300, 320)) == 1
    surge_sim.step(1)
    affected = [ally for ally in allies if ally.surge_remaining_frames > 0]
    assert len(affected) == 5
    assert all(ally.surge_attack_speed_multiplier == 0.75 for ally in affected)
    assert mage.energy == 55
    surge_sim.close()
