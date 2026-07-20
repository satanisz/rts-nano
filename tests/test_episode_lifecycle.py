"""Deterministic RL episode termination, truncation, and reset behavior."""

from __future__ import annotations

import pytest

from rts_nano.actions import NoOpAction
from rts_nano.env import RtsNanoEnv
from rts_nano.rewards import resource_gain_reward
from rts_nano.simulation.entities import TeamColor


def _settings(*, red_base: bool = True) -> dict[str, object]:
    return {
        "schema_version": 2,
        "Blue": {"faction_id": "AEGIS", "base": [[100, 100]]},
        "Red": {"faction_id": "RUST", "base": [[700, 500]] if red_base else []},
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


def test_episode_truncates_at_frame_limit_without_overshoot() -> None:
    env = RtsNanoEnv(settings=_settings(), max_episode_frames=3)
    result = env.step(NoOpAction(frames=8))

    assert result.done
    assert result.truncated
    assert not result.terminated
    assert result.observation.tick == 3
    assert result.info["frames"] == 3
    assert result.info["requested_frames"] == 8
    assert result.info["end_reason"] == "time_limit"
    with pytest.raises(RuntimeError, match="reset"):
        env.step(NoOpAction())
    env.close()


def test_natural_result_on_limit_boundary_takes_precedence() -> None:
    env = RtsNanoEnv(settings=_settings(red_base=False), max_episode_frames=1)
    result = env.step(NoOpAction())

    assert result.done
    assert result.terminated
    assert not result.truncated
    assert result.observation.game_over == "Team Blue wins"
    assert result.info["end_reason"] == "game_result"
    env.close()


def test_reset_starts_new_episode_and_clears_delta_reward_state() -> None:
    env = RtsNanoEnv(
        settings=_settings(),
        reward_fn=resource_gain_reward("Blue"),
        max_episode_frames=2,
    )
    first = env.step(NoOpAction())
    env._require_simulation().manager.teams[TeamColor.BLUE].resources["wood"] += 5
    second = env.step(NoOpAction())
    assert first.reward == 0.0
    assert second.reward == 5.0
    assert second.info["episode_id"] == 1

    env.reset(seed=9)
    after_reset = env.step(NoOpAction())
    assert after_reset.reward == 0.0
    assert after_reset.info["episode_id"] == 2
    assert after_reset.info["decision_count"] == 1
    assert after_reset.info["seed"] == 9
    env.close()


def test_disabled_limit_preserves_legacy_open_episode() -> None:
    env = RtsNanoEnv(settings=_settings(), max_episode_frames=None)
    result = env.step(NoOpAction(frames=5))
    assert not result.done
    assert result.observation.tick == 5
    env.close()


def test_repeated_resets_keep_episode_and_entity_identity_bounded() -> None:
    env = RtsNanoEnv(settings=_settings(), max_episode_frames=1)
    entity_count = len(env.observe().entities)
    for episode in range(1, 51):
        observation = env.reset(seed=episode)
        assert len(observation.entities) == entity_count
        assert observation.entities[0].id == "e0001"
        result = env.step(NoOpAction())
        assert result.info["episode_id"] == episode + 1
    env.close()


def test_episode_limit_must_be_positive_or_disabled() -> None:
    with pytest.raises(ValueError, match="positive"):
        RtsNanoEnv(settings=_settings(), max_episode_frames=0)
