"""Tests for the public headless RL environment facade."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.action_translation import ActionTranslator
from rts_nano.actions import BuildAction, CancelProductionAction, ConstructAction
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


def _settings_with_barracks() -> MapSettings:
    settings = _settings()
    settings["Blue"]["barracks"] = [[90, 60]]
    settings["Red"]["barracks"] = []
    return settings


def test_env_observation_is_serializable_snapshot() -> None:
    """Environment observations expose DTOs rather than live entities."""
    env = RtsNanoEnv(settings=_settings())

    observation = env.reset(seed=7)
    payload = observation.to_dict()

    assert observation.tick == 0
    assert payload["current_team"] == "Blue"
    assert {entity.kind for entity in observation.entities} == {"Peasant", "Base", "Wood"}
    assert env.available_actions()[0].kind == "no_op"
    assert observation.teams[0].population_cap == 10

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
    assert len(manager.production.queue_for(manager.bases_for_team(TeamColor.BLUE)[0])) == 1
    simulation.step(60)
    assert len(manager.units_for_team(TeamColor.BLUE)) == 2
    simulation.close()


def test_action_translator_applies_military_build_orders() -> None:
    """Action translator can produce military units from barracks."""
    simulation = HeadlessSimulation.from_settings(_settings_with_barracks())
    manager = simulation.manager
    manager.entities[TeamColor.BLUE].resources.update({"wood": 100, "cristal": 25})
    registry = EntityIdRegistry()
    observation = build_observation(manager, tick=0, registry=registry)
    barracks_id = next(
        entity.id for entity in observation.entities if entity.kind == "Barracks" and entity.team == "Blue"
    )

    affected = ActionTranslator(manager, registry).apply(
        BuildAction(TeamColor.BLUE, base_id=barracks_id, unit_type="knight")
    )

    assert affected == 1
    assert (
        manager.production.queue_for(manager.production_buildings_for_team(TeamColor.BLUE)[1])[0].unit_type == "knight"
    )
    simulation.step(120)
    assert len(manager.entities[TeamColor.BLUE].knights) == 1
    simulation.close()


def test_action_translator_applies_worker_construction_orders() -> None:
    """Action translator can place unfinished structures through a worker."""
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    manager.entities[TeamColor.BLUE].resources.update({"wood": 220, "cristal": 60})
    registry = EntityIdRegistry()
    observation = build_observation(manager, tick=0, registry=registry)
    builder_id = next(
        entity.id for entity in observation.entities if entity.kind == "Peasant" and entity.team == "Blue"
    )

    affected = ActionTranslator(manager, registry).apply(
        ConstructAction(TeamColor.BLUE, (160, 90), builder_id=builder_id)
    )

    assert affected == 1
    assert len(manager.entities[TeamColor.BLUE].barracks) == 1
    assert manager.entities[TeamColor.BLUE].barracks[0].is_under_construction is True
    simulation.close()


def test_env_action_mask_reports_stateful_legality() -> None:
    """Action masks expose legal action families and denial reasons."""
    env = RtsNanoEnv(settings=_settings())

    mask = env.action_mask(TeamColor.BLUE)
    specs = {(spec.kind, spec.team, spec.unit_type): spec for spec in mask}

    assert specs[("move", "Blue", None)].enabled is True
    assert specs[("gather", "Blue", None)].enabled is True
    assert specs[("build", "Blue", "peasant")].enabled is False
    assert specs[("build", "Blue", "peasant")].reason == "insufficient_resources"
    assert specs[("cancel_production", "Blue", None)].enabled is False
    construction_specs = {(spec.kind, spec.team, spec.building_type): spec for spec in mask}
    assert construction_specs[("construct", "Blue", "barracks")].enabled is False
    assert construction_specs[("construct", "Blue", "barracks")].reason == "insufficient_resources"
    assert construction_specs[("construct", "Blue", "house")].enabled is False
    assert construction_specs[("construct", "Blue", "house")].reason == "insufficient_resources"

    manager = env._require_simulation().manager
    manager.entities[TeamColor.BLUE].resources["wood"] = 50
    observation = env.observe()
    base_id = next(entity.id for entity in observation.entities if entity.kind == "Base" and entity.team == "Blue")

    env.step(BuildAction(TeamColor.BLUE, base_id=base_id, frames=0))
    specs = {(spec.kind, spec.team, spec.unit_type): spec for spec in env.action_mask(TeamColor.BLUE)}

    assert specs[("cancel_production", "Blue", None)].enabled is True

    cancel_result = env.step(CancelProductionAction(TeamColor.BLUE, base_id=base_id, frames=0))

    assert cancel_result.observation.teams[0].wood == 37

    env.close()


def test_env_construct_action_observes_unfinished_barracks() -> None:
    """Environment exposes worker construction through actions and snapshots."""
    env = RtsNanoEnv(settings=_settings())
    manager = env._require_simulation().manager
    manager.entities[TeamColor.BLUE].resources.update({"wood": 220, "cristal": 60})
    observation = env.observe()
    builder_id = next(
        entity.id for entity in observation.entities if entity.kind == "Peasant" and entity.team == "Blue"
    )

    result = env.step(ConstructAction(TeamColor.BLUE, (160, 90), builder_id=builder_id, frames=0))
    barracks = next(entity for entity in result.observation.entities if entity.kind == "Barracks")

    assert barracks.is_under_construction is True
    assert barracks.construction_progress == 0
    assert result.observation.teams[0].wood == 0
    assert result.observation.teams[0].cristal == 0

    env.close()


def test_env_constructs_house_and_reports_population_cap() -> None:
    """House construction is available through env actions and raises support on completion."""
    env = RtsNanoEnv(settings=_settings())
    manager = env._require_simulation().manager
    manager.entities[TeamColor.BLUE].resources["wood"] = 80
    observation = env.observe()
    builder_id = next(
        entity.id for entity in observation.entities if entity.kind == "Peasant" and entity.team == "Blue"
    )

    result = env.step(
        ConstructAction(TeamColor.BLUE, (160, 90), builder_id=builder_id, building_type="house", frames=0)
    )
    house = next(entity for entity in result.observation.entities if entity.kind == "House")

    assert house.is_under_construction is True
    assert result.observation.teams[0].population_cap == 10

    completed = env.step(NoOpAction(frames=320)).observation

    assert next(entity for entity in completed.entities if entity.kind == "House").is_under_construction is False
    assert completed.teams[0].population_cap == 16

    env.close()


def test_env_action_mask_reports_military_production() -> None:
    """Action masks expose barracks production as unit-specific build options."""
    env = RtsNanoEnv(settings=_settings_with_barracks())
    manager = env._require_simulation().manager
    manager.entities[TeamColor.BLUE].resources.update({"wood": 100, "cristal": 25})

    specs = {(spec.kind, spec.team, spec.unit_type): spec for spec in env.action_mask(TeamColor.BLUE)}

    assert specs[("build", "Blue", "knight")].enabled is True
    assert specs[("build", "Blue", "archer")].enabled is False
    assert specs[("build", "Blue", "archer")].reason == "insufficient_resources"

    env.close()


def test_env_replays_same_action_sequence_deterministically() -> None:
    """Same settings, seed, actions, and production queue produce same snapshots."""

    def run_sequence() -> list[dict[str, object]]:
        env = RtsNanoEnv(settings=_settings())
        observation = env.reset(seed=11)
        manager = env._require_simulation().manager
        manager.entities[TeamColor.BLUE].resources["wood"] = 50
        observation = env.observe()
        base_id = next(entity.id for entity in observation.entities if entity.kind == "Base" and entity.team == "Blue")
        actions = (
            MoveAction(TeamColor.BLUE, (120, 120)),
            BuildAction(TeamColor.BLUE, base_id=base_id, frames=1),
            NoOpAction(frames=60),
        )
        snapshots = [observation.to_dict()]
        for action in actions:
            snapshots.append(env.step(action).observation.to_dict())
        env.close()
        return snapshots

    first_run = run_sequence()
    assert first_run == run_sequence()
    assert first_run[-1]["teams"][0]["units"] == 2
