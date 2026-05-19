"""Tests for the public headless RL environment facade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.action_translation import ActionTranslator
from rts_nano.actions import BuildAction
from rts_nano.env import MoveAction, NoOpAction, RtsNanoEnv
from rts_nano.game.assets.entities import TeamColor
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.headless import HeadlessSimulation

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


def test_observation_builder_keeps_stable_entity_ids() -> None:
    """Observation builder owns stable IDs outside the environment facade."""
    simulation = HeadlessSimulation.from_settings(_settings())
    registry = EntityIdRegistry()

    first = build_observation(simulation.manager, tick=0, registry=registry)
    second = build_observation(simulation.manager, tick=1, registry=registry)

    assert first.tick == 0
    assert second.tick == 1
    assert [entity.id for entity in first.entities] == [entity.id for entity in second.entities]

    simulation.close()


def test_action_translator_applies_build_orders() -> None:
    """Action translator applies DTOs through the manager order system."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    manager.entities[TeamColor.BLUE].resources["wood"] = 50
    registry = EntityIdRegistry()
    observation = build_observation(manager, tick=0, registry=registry)
    base_id = next(entity.id for entity in observation.entities if entity.kind == "Base" and entity.team == "Blue")

    affected = ActionTranslator(manager, registry).apply(BuildAction(TeamColor.BLUE, base_id=base_id))

    assert affected == 1
    assert len(manager.units_for_team(TeamColor.BLUE)) == 2
    simulation.close()


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
