"""Tests for headless benchmark and batch helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.benchmark import measure_steps_per_second, run_batch
from rts_nano.rewards import win_loss_reward
from rts_nano.simulation.entities.base import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [[20, 20]],
            "base": [[60, 60]],
            "guardian": [],
            "marksman": [],
            "arclight": [],
        },
        "Red": {"faction_id": "RUST", "peasant": [], "base": [[250, 250]], "ripper": [], "spitter": [], "brute": []},
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 400,
            "height": 300,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def test_measure_steps_per_second_runs_and_reports_throughput() -> None:
    """The benchmark advances the requested steps and reports positive throughput."""
    result = measure_steps_per_second(steps=50, settings=_settings())

    assert result.steps == 50
    assert result.elapsed_seconds >= 0.0
    assert result.steps_per_second > 0.0


def test_run_batch_collects_reward_per_environment() -> None:
    """The batch runner returns one reward total per environment."""
    totals = run_batch(
        num_envs=3,
        steps=10,
        settings=_settings(),
        reward_fn=win_loss_reward("Blue"),
    )

    assert len(totals) == 3
    assert all(total == 0.0 for total in totals)


def test_run_batch_rewards_terminal_win() -> None:
    """A batch environment that reaches a win accrues the terminal reward once."""
    settings = _settings()
    settings["Red"]["base"] = []
    totals = run_batch(
        num_envs=1,
        steps=4,
        settings=settings,
        reward_fn=win_loss_reward("Blue"),
    )

    assert totals[0] == 1.0


def test_fog_state_marks_cells_around_team_units() -> None:
    """The env fog helper marks visible cells near a team's entities."""
    from rts_nano.env import RtsNanoEnv

    env = RtsNanoEnv(settings=_settings())
    grid = env.fog_state(TeamColor.BLUE)

    assert len(grid) > 0
    assert any(cell == 2 for row in grid for cell in row)

    env.close()
