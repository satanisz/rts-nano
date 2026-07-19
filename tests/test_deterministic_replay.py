"""Versioned golden replay protecting core gameplay behavior during refactors."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import Arclight, Guardian, Marksman, Spitter, TeamColor

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.map_schema import MapSettings
    from rts_nano.simulation.entities.base import Entity

GOLDEN_PATH = Path(__file__).with_name("golden") / "core_replay_v1.json"
EXPECTED_SHA256 = "0b2cdca727b2b45b388fe026e7949dc53268bb12942d57667be69dcf8d1ec167"


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [[100, 130]],
            "base": [[100, 80]],
            "guardian": [[300, 300]],
            "marksman": [],
            "arclight": [[350, 300]],
            "arsenal": [[150, 80]],
            "spire": [[200, 80]],
            "bastion": [[250, 80]],
        },
        "Red": {
            "faction_id": "RUST",
            "peasant": [[650, 500]],
            "base": [[700, 500]],
            "ripper": [[455, 300]],
            "spitter": [[430, 300]],
            "brute": [[520, 300]],
            "pit": [[650, 550]],
            "chem_vat": [[600, 550]],
            "spiker": [[520, 500]],
        },
        "Resources": {"wood": [[140, 130]], "gold": [[170, 130]]},
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


def _one(manager: GameSession, team: TeamColor, entity_type: type[Entity]) -> Entity:
    return next(entity for entity in manager.state.entities_for_team(team) if isinstance(entity, entity_type))


def _position(entity: Entity) -> list[float]:
    return [round(entity.x, 3), round(entity.y, 3)]


def run_core_replay() -> dict[str, object]:
    """Run one deterministic scenario and return compact, readable checkpoints."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    blue = manager.teams[TeamColor.BLUE]
    worker = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
    guardian = _one(manager, TeamColor.BLUE, Guardian)
    arclight = _one(manager, TeamColor.BLUE, Arclight)
    spitter = _one(manager, TeamColor.RED, Spitter)
    ripper = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]
    wood = manager.state.resources_by_content("wood")[0]
    checkpoints: dict[str, object] = {}
    tick = 0

    try:
        manager.issue_move_order(TeamColor.BLUE, (320, 300), [guardian])
        simulation.step(12)
        tick += 12
        checkpoints["movement"] = {
            "tick": tick,
            "guardian_position": _position(guardian),
            "guardian_state": guardian.state,
        }

        manager.issue_gather_order(TeamColor.BLUE, wood, [worker])
        simulation.step(90)
        tick += 90
        checkpoints["economy"] = {
            "tick": tick,
            "bank": dict(blue.resources),
            "worker_position": _position(worker),
            "worker_state": worker.state,
            "worker_carry": {"wood": worker.carry_wood, "gold": worker.carry_gold},
            "wood_remaining": wood.amount,
        }

        blue.resources.update({"wood": 500, "gold": 300})
        assert manager.construct_building(worker, "house", (100, 200))
        simulation.step(220)
        tick += 220
        house = manager.state.entities_by_content_id("house", team=TeamColor.BLUE)[0]
        checkpoints["construction"] = {
            "tick": tick,
            "bank": dict(blue.resources),
            "house_life": house.life,
            "house_complete": not house.is_under_construction,
            "population_cap": manager.population_cap_for_team(TeamColor.BLUE),
            "worker_state": worker.state,
        }

        arsenal = manager.state.entities_by_content_id("arsenal", team=TeamColor.BLUE)[0]
        assert manager.produce_unit(arsenal, "marksman")
        simulation.step(121)
        tick += 121
        marksman = _one(manager, TeamColor.BLUE, Marksman)
        checkpoints["production"] = {
            "tick": tick,
            "bank": dict(blue.resources),
            "marksman_position": _position(marksman),
            "marksman_life": marksman.life,
            "queued_units": manager.production.queued_units_for_team(TeamColor.BLUE),
        }

        spitter_life_before = spitter.life
        ripper_life_before = ripper.life
        manager.issue_target_order(TeamColor.BLUE, spitter, [arclight])
        simulation.step(1)
        tick += 1
        splash_checkpoint = {
            "spitter_damage": spitter_life_before - spitter.life,
            "ripper_splash_damage": ripper_life_before - ripper.life,
        }

        shield_before = guardian.shield
        manager.issue_target_order(TeamColor.RED, guardian, [spitter])
        simulation.step(31)
        tick += 31
        checkpoints["combat_mechanics"] = {
            "tick": tick,
            **splash_checkpoint,
            "guardian_life": guardian.life,
            "guardian_shield_before": shield_before,
            "guardian_shield_after": guardian.shield,
            "guardian_poison_remaining": guardian.poison_remaining_frames,
            "spitter_life": spitter.life,
            "ripper_life": ripper.life,
        }

        for entity in manager.state.entities_for_team(TeamColor.RED):
            entity.life = 0
        simulation.step(1)
        tick += 1
        checkpoints["victory"] = {
            "tick": tick,
            "result": manager.game_over_message,
            "paused": manager.paused,
            "blue_units": manager.state.count_units(TeamColor.BLUE),
            "red_entities": len(manager.state.entities_for_team(TeamColor.RED)),
        }
    finally:
        simulation.close()

    return {"schema_version": 1, "checkpoints": checkpoints}


def _digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def test_core_replay_matches_readable_golden_snapshot() -> None:
    """Gameplay checkpoints produce a readable diff when behavior changes."""
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    assert run_core_replay() == expected


def test_core_replay_is_repeatable_and_matches_stored_digest() -> None:
    """Two fresh simulations produce the same versioned gameplay digest."""
    first = run_core_replay()
    second = run_core_replay()

    assert first == second
    assert _digest(first) == EXPECTED_SHA256
