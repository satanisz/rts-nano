"""Tests for the public headless RL environment facade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.env import MoveAction, NoOpAction, RtsNanoEnv
from rts_nano.game.assets.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "Blue": {"peasant": [[20, 20]], "base": [[60, 60]], "knight": [], "archer": [], "mage": []},
        "Red": {"peasant": [], "base": [[250, 250]], "knight": [], "archer": [], "mage": []},
        "Resources": {"wood": [[160, 20]], "cristal": []},
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


def test_env_observation_is_serializable_snapshot() -> None:
    """Environment observations expose DTOs rather than live entities."""
    env = RtsNanoEnv(settings=_settings())

    observation = env.reset(seed=7)
    payload = observation.to_dict()

    assert observation.tick == 0
    assert payload["current_team"] == "Blue"
    assert {entity.kind for entity in observation.entities} == {"Peasant", "Base", "Wood"}
    assert env.available_actions()[0].kind == "no_op"

    env.close()


def test_env_replays_same_action_sequence_deterministically() -> None:
    """Same settings, seed, and actions produce the same snapshot sequence."""
    actions = (
        MoveAction(TeamColor.BLUE, (120, 120)),
        NoOpAction(frames=2),
    )

    def run_sequence() -> list[dict[str, object]]:
        env = RtsNanoEnv(settings=_settings())
        snapshots = [env.reset(seed=11).to_dict()]
        for action in actions:
            snapshots.append(env.step(action).observation.to_dict())
        env.close()
        return snapshots

    assert run_sequence() == run_sequence()
