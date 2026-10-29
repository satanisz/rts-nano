"""Bounded memoization of unchanged failed scouting paths preserves bot behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rts_nano.ai import ScriptedAI
from rts_nano.application import GameSession
from rts_nano.game.entity_factory import EntityFactory
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.game.order import Order
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.simulation.entities.base import Unit


def _game() -> GameSession:
    return GameSession(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[540, 400]], "peasant": []},
            "Red": {
                "faction_id": "RUST",
                "base": [[80, 80]],
                "peasant": [],
                "ripper": [[120, 200], [150, 200], [180, 200]],
            },
            "Resources": {"wood": [], "gold": []},
            "Terrain": {
                "width": 640,
                "height": 480,
                "water": [[[300, 0, 40, 480]]],
                "rocks": [],
                "ramps": [],
                "high_ground": [],
                "grass": [],
            },
        }
    )


def test_repeated_failed_scouting_matches_uncached_gameplay_with_one_path_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cached, reference = _game(), _game()
    bot, uncached_bot = (
        ScriptedAI(cached, TeamColor.RED, decision_interval=1),
        ScriptedAI(reference, TeamColor.RED, decision_interval=1),
    )
    monkeypatch.setattr(bot, "_nearest_unexplored_point", lambda _origin: (480, 200))
    monkeypatch.setattr(uncached_bot, "_nearest_unexplored_point", lambda _origin: (480, 200))
    attempts: list[tuple[float, float]] = []
    original = cached.movement.find_unit_path

    def find_path(unit: Unit, destination: tuple[float, float]) -> list[tuple[float, float]]:
        attempts.append(destination)
        return original(unit, destination)

    monkeypatch.setattr(cached.movement, "find_unit_path", find_path)
    for _ in range(20):
        bot.step()
        cached.update()
        uncached_bot._failed_scout_request = None
        uncached_bot.step()
        reference.update()
        assert build_observation(cached, cached.state.tick_count, EntityIdRegistry()) == build_observation(
            reference, reference.state.tick_count, EntityIdRegistry()
        )
    assert attempts == [(480, 200)]
    assert bot._vision.grid == uncached_bot._vision.grid
    assert bot.known_enemy_base_position == uncached_bot.known_enemy_base_position


@pytest.mark.parametrize("change", ["goal", "position", "scout", "building", "terrain", "target", "order", "queue"])
def test_failed_scout_search_retries_after_relevant_changes(monkeypatch: pytest.MonkeyPatch, change: str) -> None:
    game = _game()
    bot = ScriptedAI(game, TeamColor.RED)
    goal = [480, 200]
    monkeypatch.setattr(bot, "_nearest_unexplored_point", lambda _origin: (goal[0], goal[1]))
    attempts: list[tuple[float, float]] = []
    original = game.movement.find_unit_path

    def find_path(unit: Unit, destination: tuple[float, float]) -> list[tuple[float, float]]:
        attempts.append(destination)
        return original(unit, destination)

    monkeypatch.setattr(game.movement, "find_unit_path", find_path)
    army = game.units_for_team(TeamColor.RED)
    scout = army[0]
    bot._scout_unexplored(army)
    bot._scout_unexplored(army)
    assert len(attempts) == 1
    if change == "goal":
        goal[1] += 40
    elif change == "position":
        scout.x += 1
    elif change == "scout":
        army[1].x, army[1].y = scout.get_center()
        army = army[1:]
    elif change == "building":
        game.state.add_runtime_entity(EntityFactory.create("house", 80, 350, TeamColor.RED))
    elif change == "terrain":
        game.terrain.water.clear()
    elif change == "target":
        game.state.add_runtime_entity(EntityFactory.create("guardian", 480, 200, TeamColor.BLUE))
    elif change == "order":
        scout.current_order = Order("hold")
        scout.state = "HOLDING"
    elif change == "queue":
        scout.order_queue.append(Order("move", (100, 100)))
    bot._scout_unexplored(army)
    assert len(attempts) == 2
    if change == "terrain":
        assert not scout.path_unreachable
        assert scout.state == "MOVING"
