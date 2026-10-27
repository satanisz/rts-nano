"""C3 simulation-owned match endings, pause, restart, and legacy-wrapper compatibility."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from rts_nano.actions import NoOpAction
from rts_nano.env import RtsNanoEnv
from rts_nano.game.match import DEFAULT_MATCH_FRAMES, MatchRules
from rts_nano.game.ui.match_result import match_clock_label, match_result_detail
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {"faction_id": "AEGIS", "base": [[80, 80]]},
        "Red": {"faction_id": "RUST", "base": [[700, 500]]},
        "Resources": {"wood": [], "gold": []},
        "Terrain": {"width": 800, "height": 600, "water": [], "rocks": [], "ramps": [], "high_ground": [], "grass": []},
    }


@pytest.mark.parametrize("scenario", ["houses", "isolated", "depleted", "no_base"])
def test_nonwinning_states_draw_at_the_game_limit(scenario: str) -> None:
    settings = _settings()
    if scenario == "houses":
        settings["Blue"] = {"faction_id": "AEGIS", "house": [[80, 80]]}
        settings["Red"] = {"faction_id": "RUST", "house": [[700, 500]]}
    elif scenario in {"isolated", "no_base"}:
        settings["Blue"] = {"faction_id": "AEGIS", "peasant": [[80, 80]]}
        settings["Red"] = {"faction_id": "RUST", "peasant": [[700, 500]]}
        if scenario == "isolated":
            settings["Terrain"]["water"] = [[[380, 0, 40, 600]]]
    sim = HeadlessSimulation.from_settings(settings, match_rules=MatchRules(max_frames=3))
    if scenario == "isolated":
        sim.issue_move_order(TeamColor.BLUE, (700, 500))
    assert sim.step(2) == 2
    assert sim.manager.game_over_message is None
    assert sim.step(10) == 1
    assert sim.manager.state.tick_count == 3
    assert sim.manager.game_over_message == "Draw"
    assert sim.manager.state.match_end_reason == "time_limit"
    assert sim.manager.paused
    assert match_result_detail(sim.manager) == "Time limit reached."
    assert sim.step(10) == 0


def test_default_ten_minute_game_limit_is_enforced_without_an_environment() -> None:
    sim = HeadlessSimulation.from_settings(_settings())
    assert match_clock_label(sim.manager) == "Time 0:00 / 10:00"
    assert sim.step(DEFAULT_MATCH_FRAMES + 5) == DEFAULT_MATCH_FRAMES
    assert sim.manager.game_over_message == "Draw"
    assert match_clock_label(sim.manager) == "Time 10:00 / 10:00"


@pytest.mark.parametrize("mutual", [False, True])
def test_elimination_on_final_tick_precedes_timeout(mutual: bool) -> None:
    sim = HeadlessSimulation.from_settings(_settings(), match_rules=MatchRules(max_frames=2))
    sim.step()
    sim.manager.bases_for_team(TeamColor.RED)[0].life = 0
    if mutual:
        sim.manager.bases_for_team(TeamColor.BLUE)[0].life = 0
    assert sim.step(10) == 1
    assert sim.manager.game_over_message == ("Draw" if mutual else "Team Blue wins")
    assert sim.manager.state.match_end_reason == "elimination"


def test_combat_result_on_final_tick_wins_before_timeout() -> None:
    settings = _settings()
    settings["Blue"]["guardian"] = [[400, 300]]
    settings["Red"] = {"faction_id": "RUST", "peasant": [[420, 300]]}
    sim = HeadlessSimulation.from_settings(settings, match_rules=MatchRules(max_frames=1))
    target = sim.units_for_team(TeamColor.RED)[0]
    target.life = 1
    sim.manager.issue_target_order(TeamColor.BLUE, target)
    sim.step()
    assert sim.manager.game_over_message == "Team Blue wins"
    assert sim.manager.state.match_end_reason == "elimination"


def test_pause_freezes_clock_and_restart_preserves_rules_without_terminal_state() -> None:
    sim = HeadlessSimulation.from_settings(_settings(), match_rules=MatchRules(max_frames=3))
    sim.step()
    sim.manager.paused = True
    assert sim.step(50) == 0
    assert sim.manager.state.tick_count == 1
    sim.manager.paused = False
    sim.step(50)
    sim.manager.paused = False  # Even an accidental unpause cannot reopen a terminal match.
    assert sim.step() == 0
    sim.manager.simulation.step()
    assert sim.manager.state.tick_count == 3
    sim.manager.update()
    assert sim.manager.paused
    restarted = sim.manager.restart()
    assert restarted.state.match_rules == MatchRules(max_frames=3)
    assert restarted.state.tick_count == 0
    assert restarted.state.match_end_reason is None
    assert restarted.game_over_message is None
    assert not restarted.paused
    assert HeadlessSimulation(restarted).step(10) == 3


def test_result_is_latched_and_base_loss_alone_is_not_elimination() -> None:
    settings = _settings()
    settings["Red"]["house"] = [[500, 500]]
    sim = HeadlessSimulation.from_settings(settings, match_rules=MatchRules(max_frames=2))
    sim.manager.bases_for_team(TeamColor.RED)[0].life = 0
    sim.step()
    assert sim.manager.game_over_message is None
    sim.step()
    for entity in sim.manager.state.entities_for_team(TeamColor.RED):
        entity.life = 0
    sim.manager.victory.update()
    assert sim.manager.game_over_message == "Draw"
    assert sim.manager.state.match_end_reason == "time_limit"


@pytest.mark.parametrize("invalid", [0, -1, True, 1.5])
def test_invalid_match_limits_are_rejected(invalid: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        MatchRules(max_frames=invalid)


def test_explicit_unbounded_elimination_and_existing_episode_semantics() -> None:
    sim = HeadlessSimulation.from_settings(_settings(), match_rules=MatchRules(max_frames=None))
    sim.manager.state.tick_count = DEFAULT_MATCH_FRAMES
    assert sim.step() == 1
    assert sim.manager.game_over_message is None
    assert match_clock_label(sim.manager) == "Time 10:00"

    env = RtsNanoEnv(settings=_settings())
    result = env.step(NoOpAction(frames=DEFAULT_MATCH_FRAMES + 1))
    assert result.truncated
    assert not result.terminated
    assert result.observation.game_over is None
    assert result.observation.tick == DEFAULT_MATCH_FRAMES
    assert result.info["end_reason"] == "time_limit"
    env.close()
