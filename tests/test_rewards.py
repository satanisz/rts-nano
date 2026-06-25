"""Tests for the composable reward function library."""

from __future__ import annotations

from rts_nano.game.observations import Observation, TeamSnapshot
from rts_nano.rewards import combine, enemy_losses_reward, resource_gain_reward, win_loss_reward


def _observation(*, teams: tuple[TeamSnapshot, ...], game_over: str | None = None) -> Observation:
    return Observation(
        tick=0,
        map_width=100,
        map_height=100,
        current_team="Blue",
        game_over=game_over,
        teams=teams,
        entities=(),
    )


def _team(name: str, *, wood: int = 0, gold: int = 0, units: int = 0, buildings: int = 0) -> TeamSnapshot:
    return TeamSnapshot(
        team=name,
        wood=wood,
        gold=gold,
        units=units,
        buildings=buildings,
        population_cap=10,
        queued_units=0,
    )


def test_win_loss_reward_scores_terminal_states() -> None:
    """Win/loss/draw map to configured scores and non-terminal states score zero."""
    reward = win_loss_reward("Blue", win=1.0, loss=-1.0, draw=0.5)
    teams = (_team("Blue"), _team("Red"))

    assert reward(_observation(teams=teams)) == 0.0
    assert reward(_observation(teams=teams, game_over="Team Blue wins")) == 1.0
    assert reward(_observation(teams=teams, game_over="Team Red wins")) == -1.0
    assert reward(_observation(teams=teams, game_over="Draw")) == 0.5


def test_resource_gain_reward_returns_step_delta() -> None:
    """Resource reward returns zero on the first step then the banked increase."""
    reward = resource_gain_reward("Blue", wood_weight=1.0, gold_weight=2.0)

    assert reward(_observation(teams=(_team("Blue", wood=10, gold=0),))) == 0.0
    assert reward(_observation(teams=(_team("Blue", wood=15, gold=3),))) == 11.0


def test_enemy_losses_reward_rewards_destroying_rivals() -> None:
    """Enemy-loss reward is positive when rival unit/building counts drop."""
    reward = enemy_losses_reward("Blue", unit_weight=1.0, building_weight=2.0)

    assert reward(_observation(teams=(_team("Blue"), _team("Red", units=3, buildings=2)))) == 0.0
    assert reward(_observation(teams=(_team("Blue"), _team("Red", units=1, buildings=2)))) == 2.0


def test_combine_applies_weights() -> None:
    """Combine produces a weighted sum of its component rewards."""
    reward = combine(
        [win_loss_reward("Blue"), resource_gain_reward("Blue")],
        weights=[10.0, 1.0],
    )
    teams_start = (_team("Blue", wood=0),)
    teams_after = (_team("Blue", wood=5),)

    assert reward(_observation(teams=teams_start)) == 0.0
    assert reward(_observation(teams=teams_after, game_over="Team Blue wins")) == 15.0
