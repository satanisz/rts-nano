"""Frozen public type and single-player boundaries for Executive Plan 07."""

from __future__ import annotations

from rts_nano.env import ActionOutcome, EpisodeEndReason, JointStepResult
from rts_nano.game.observations import Observation


def _observation() -> Observation:
    return Observation(
        tick=0,
        map_width=100,
        map_height=100,
        current_team="Blue",
        game_over=None,
        teams=(),
        entities=(),
    )


def test_joint_result_done_combines_termination_and_truncation() -> None:
    outcome = ActionOutcome(0, "Blue", "move", accepted=False, reason="invalid_target")
    active = JointStepResult(_observation(), {"Blue": 0.0, "Red": 0.0}, False, False, (outcome,), {})
    terminated = JointStepResult(_observation(), {}, True, False, (), {})
    truncated = JointStepResult(_observation(), {}, False, True, (), {})

    assert not active.done
    assert terminated.done
    assert truncated.done
    assert EpisodeEndReason.GAME_RESULT.value == "game_result"
    assert EpisodeEndReason.TIME_LIMIT.value == "time_limit"
