"""Readable golden replay for researched doctrines and Mage casting."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import Archer, Mage, TeamColor

GOLDEN_PATH = Path(__file__).with_name("golden") / "technology_replay_v1.json"
EXPECTED_SHA256 = "0f5c00aeb392c44da98a41711128cd40a35396b227628dcc3b7469fab1671cda"


def run_technology_replay() -> dict[str, object]:
    """Run deterministic AEGIS control and RUST area-attrition doctrine paths."""
    simulation = HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {
                "faction_id": "AEGIS",
                "base": [[100, 100]],
                "arsenal": [[160, 100]],
                "spire": [[220, 100]],
                "archer": [[260, 300]],
                "mage": [[300, 300]],
                "arclight": [[220, 300]],
            },
            "Red": {
                "faction_id": "RUST",
                "base": [[700, 500]],
                "chem_vat": [[640, 500]],
                "knight": [[390, 300]],
                "mage": [[450, 300]],
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
    manager = simulation.manager
    archer = manager.state.entities_by_content_id("archer", team=TeamColor.BLUE)[0]
    mage = manager.state.entities_by_content_id("mage", team=TeamColor.BLUE)[0]
    enemy = manager.state.entities_by_content_id("knight", team=TeamColor.RED)[0]
    rust_mage = manager.state.entities_by_content_id("mage", team=TeamColor.RED)[0]
    assert isinstance(archer, Archer)
    assert isinstance(mage, Mage)
    assert isinstance(rust_mage, Mage)
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_archer_arcshot")
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_arc_targeting")
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_mage_arcbinder")
    assert manager.issue_target_order(TeamColor.BLUE, enemy, [archer]) == 1
    simulation.step()
    assert manager.issue_cast_order(TeamColor.BLUE, "arc_bind", mage, target=enemy) == 1
    simulation.step()
    assert manager.upgrades.complete(TeamColor.RED, "rust_mage_plaguecaller")
    assert manager.issue_cast_order(TeamColor.RED, "toxic_cloud", rust_mage, destination=archer.get_center()) == 1
    simulation.step()

    snapshot: dict[str, object] = {
        "schema_version": 1,
        "tick": manager.state.tick_count,
        "completed_upgrades": {
            "AEGIS": [str(item) for item in manager.teams[TeamColor.BLUE].completed_upgrades],
            "RUST": [str(item) for item in manager.teams[TeamColor.RED].completed_upgrades],
        },
        "mage": {
            "energy": mage.energy,
            "cooldowns": dict(sorted(mage.ability_cooldowns.items())),
            "order": mage.current_order.kind if mage.current_order is not None else None,
        },
        "enemy": {
            "life": enemy.life,
            "arc_mark_frames": enemy.arc_mark_remaining_frames,
            "arc_mark_team": enemy.arc_mark_team.value if enemy.arc_mark_team is not None else None,
            "slow_frames": enemy.slow_remaining_frames,
            "speed": enemy.speed,
        },
        "rust_mage": {
            "energy": rust_mage.energy,
            "cooldowns": dict(sorted(rust_mage.ability_cooldowns.items())),
        },
        "cross_faction_poison": {
            "damage": archer.poison_tick_damage,
            "remaining_frames": archer.poison_remaining_frames,
        },
    }
    simulation.close()
    return snapshot


def _digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def test_technology_replay_matches_readable_golden() -> None:
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    assert run_technology_replay() == expected


def test_technology_replay_is_repeatable() -> None:
    first = run_technology_replay()
    assert first == run_technology_replay()
    assert _digest(first) == EXPECTED_SHA256
