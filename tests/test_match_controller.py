"""Application participant composition and lifecycle for play/spectate modes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from rts_nano.ai import ScriptedAI
from rts_nano.application import GameSession, MatchController, MatchMode
from rts_nano.game.match import MatchRules
from rts_nano.map_schema import load_map_settings
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return load_map_settings(Path("src/rts_nano/maps/map_spec_01.json"))


@pytest.mark.parametrize(
    ("mode", "expected"),
    [(MatchMode.PLAY, (TeamColor.RED,)), (MatchMode.SPECTATE, (TeamColor.BLUE, TeamColor.RED))],
)
def test_participants_decide_in_stable_order_before_each_tick(
    monkeypatch: pytest.MonkeyPatch, mode: MatchMode, expected: tuple[TeamColor, ...]
) -> None:
    decisions: list[tuple[TeamColor, int]] = []

    def decide(bot: ScriptedAI) -> None:
        decisions.append((bot._team, bot._manager.state.tick_count))

    monkeypatch.setattr(ScriptedAI, "step", decide)
    match = MatchController(GameSession(_settings()), mode)
    match.step()
    match.step()

    assert decisions == [(team, tick) for tick in (0, 1) for team in expected]
    assert match.session.state.tick_count == 2


def test_pause_and_result_stop_bot_decisions_as_well_as_game_ticks(monkeypatch: pytest.MonkeyPatch) -> None:
    decisions: list[int] = []
    monkeypatch.setattr(ScriptedAI, "step", lambda _bot: decisions.append(1))
    match = MatchController(GameSession(_settings(), match_rules=MatchRules(max_frames=2)), MatchMode.SPECTATE)
    match.session.paused = True
    match.step()
    assert not decisions
    assert match.session.state.tick_count == 0

    match.session.paused = False
    match.step()
    match.step()
    assert match.session.game_over_message == "Draw"
    match.session.paused = False
    match.step()
    assert len(decisions) == 4
    assert match.session.state.tick_count == 2


def test_restart_recreates_both_bot_memories_and_preserves_mode_and_rules() -> None:
    match = MatchController(GameSession(_settings(), match_rules=MatchRules(max_frames=100)), MatchMode.SPECTATE)
    for _ in range(20):
        match.step()
    match.session.teams[TeamColor.BLUE].resources["gold"] = 777
    match._bots[0]._last_known_enemy_base = (100, 100)
    match.session.set_viewport_size(1280, 720)
    restarted = match.restart()

    assert restarted.mode == MatchMode.SPECTATE
    assert restarted.session is not match.session
    assert restarted.session.state.match_rules == match.session.state.match_rules
    assert restarted.session.map_settings == match.session.map_settings
    assert restarted.session.screen_width == 1280
    assert restarted.session.state.tick_count == 0
    assert restarted.session.teams[TeamColor.BLUE].resources == {"wood": 0, "gold": 0}
    assert len(restarted._bots) == 2
    assert all(new is not old and new._frame == 0 for new, old in zip(restarted._bots, match._bots, strict=True))
    assert all(bot.known_enemy_base_position is None for bot in restarted._bots)
    assert all(bot._failed_scout_request is None for bot in restarted._bots)


def test_both_real_bots_develop_from_the_original_zero_bank_start() -> None:
    match = MatchController(GameSession(_settings()), MatchMode.SPECTATE)
    for _ in range(4000):
        match.step()

    for team, producer in ((TeamColor.BLUE, "arsenal"), (TeamColor.RED, "pit")):
        assert match.session.state.entities_by_content_id(producer, team=team)
        assert any(str(unit.content_id) != "peasant" for unit in match.session.units_for_team(team))
