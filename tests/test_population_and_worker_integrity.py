"""Closeout C1 regression scenarios for weighted supply and worker death."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rts_nano.ai import ScriptedAI
from rts_nano.application import GameSession
from rts_nano.game.entity_factory import EntityFactory
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.simulation.entities.base import Entity


def _session() -> GameSession:
    game = GameSession(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[80, 80]], "arsenal": [[250, 250]], "spire": [[400, 250]]},
            "Red": {"faction_id": "RUST", "base": [[900, 700]]},
            "Resources": {"wood": [], "gold": []},
            "Terrain": {
                "width": 1000,
                "height": 800,
                "water": [],
                "rocks": [],
                "ramps": [],
                "high_ground": [],
                "grass": [],
            },
        }
    )
    game.teams[TeamColor.BLUE].resources.update(wood=10000, gold=10000)
    return game


def _add(game: GameSession, content_id: str, x: int = 600, y: int = 100) -> Entity:
    entity = EntityFactory.create(content_id, x, y, TeamColor.BLUE)
    game.state.add_runtime_entity(entity)
    return entity


def test_mixed_army_uses_weighted_population_and_dead_units_release_supply() -> None:
    game = _session()
    worker = _add(game, "peasant")
    _add(game, "knight", 650)
    for x in (700, 750):
        _add(game, "arclight", x)
    producer = game.state.entities_by_content_id("spire")[0]
    assert game.state.count_units(TeamColor.BLUE) == 4
    assert game.state.population_for_team(TeamColor.BLUE) == 9
    assert game.production.can_enqueue_unit(producer, "arclight") == (False, "population_cap")
    _add(game, "peasant", 800)
    base = game.bases_for_team(TeamColor.BLUE)[0]
    before = game.teams[TeamColor.BLUE].resources.copy()
    assert not game.produce_unit(base, "peasant")
    assert game.teams[TeamColor.BLUE].resources == before
    worker.life = 0
    assert game.state.population_for_team(TeamColor.BLUE) == 9
    assert game.produce_unit(base, "peasant")
    assert game._has_reached_unit_cap(TeamColor.BLUE)


def test_reservations_transfer_to_spawn_across_producers_and_cancellation() -> None:
    game = _session()
    arsenal = game.state.entities_by_content_id("arsenal")[0]
    spire = game.state.entities_by_content_id("spire")[0]
    base = game.bases_for_team(TeamColor.BLUE)[0]
    for _ in range(3):
        assert game.produce_unit(spire, "arclight")
    assert game.produce_unit(base, "peasant")
    assert not game.produce_unit(arsenal, "knight")
    assert game.production.queued_population_for_team(TeamColor.BLUE) == 10
    game.production.queue_for(spire)[0].remaining_frames = 1
    game.update()
    assert game.state.population_for_team(TeamColor.BLUE) == 3
    assert game.production.queued_population_for_team(TeamColor.BLUE) == 7
    assert not game.produce_unit(arsenal, "knight")
    assert game.cancel_production(spire)
    assert game.production.queued_population_for_team(TeamColor.BLUE) == 4
    assert game.produce_unit(arsenal, "knight")
    before = game.teams[TeamColor.BLUE].resources.copy()
    spire.life = 0
    game.update()
    assert not game.production.queue_for(spire)
    assert game.production.queued_population_for_team(TeamColor.BLUE) == 3
    assert game.teams[TeamColor.BLUE].resources == before


def test_supply_loss_keeps_paid_jobs_and_existing_army_but_blocks_new_orders() -> None:
    game = _session()
    house = _add(game, "house", 600, 300)
    spire = game.state.entities_by_content_id("spire")[0]
    for x in (500, 550, 600):
        _add(game, "arclight", x)
    assert game.produce_unit(spire, "arclight")
    house.life = 0
    game.production.queue_for(spire)[0].remaining_frames = 1
    game.update()
    assert game.state.population_for_team(TeamColor.BLUE) == 12
    assert game.population_cap_for_team(TeamColor.BLUE) == 10
    assert not game.production.queue_for(spire)
    assert game.production.can_enqueue_unit(spire, "arclight") == (False, "population_cap")
    assert all(value >= 0 for value in game.teams[TeamColor.BLUE].resources.values())


def test_scripted_bot_launches_a_supply_blocked_small_army() -> None:
    game = _session()
    for x in (500, 550, 600):
        _add(game, "peasant", x)
    army = [_add(game, "guardian", x, 200) for x in (600, 650)]
    assert game.state.population_for_team(TeamColor.BLUE) == 9
    bot = ScriptedAI(game, TeamColor.BLUE, decision_interval=1)
    bot.step()
    assert any(unit.attack_move_destination is not None for unit in army)


@pytest.mark.parametrize("repair", [False, True])
@pytest.mark.parametrize("combat_death", [False, True])
def test_dead_worker_cannot_finish_building_or_spend_repair_resources(repair: bool, combat_death: bool) -> None:
    game = _session()
    worker = _add(game, "peasant", 120, 100)
    building = _add(game, "house", 180, 100)
    if repair:
        building.life -= 10
        worker.state = "REPAIRING"
    else:
        building.start_construction(1)
        worker.state = "BUILDING"
    worker.target_entity = building
    worker.life = 1 if combat_death else 0
    if combat_death:
        enemy = EntityFactory.create("ripper", 140, 100, TeamColor.RED)
        game.state.add_runtime_entity(enemy)
        enemy.attack_damage = 999
        game.issue_target_order(TeamColor.RED, worker, [enemy])
    before = (building.life, building.construction_remaining_frames, game.teams[TeamColor.BLUE].resources.copy())
    game.update()
    assert worker not in game.all_entities
    assert (building.life, building.construction_remaining_frames, game.teams[TeamColor.BLUE].resources) == before
    assert game.construction.active_builder_count(building) == 0
    assert game.construction.active_repairer_count(building) == 0
