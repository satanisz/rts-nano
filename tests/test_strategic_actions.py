"""Coverage for the complete strategic action surface exposed to RL."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.action_translation import ActionTranslator
from rts_nano.actions import (
    AssistConstructionAction,
    CancelActivityAction,
    RepairAction,
    ResearchAction,
    SetRallyAction,
)
from rts_nano.content import CONTENT
from rts_nano.env import RtsNanoEnv
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [[80, 100], [100, 100]],
            "base": [[50, 50]],
            "arsenal": [[180, 100]],
        },
        "Red": {"faction_id": "RUST", "base": [[380, 250]], "peasant": [[330, 230]]},
        "Resources": {"wood": [[220, 40]], "gold": [[250, 40]]},
        "Terrain": {
            "width": 450,
            "height": 300,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def _ids(simulation: HeadlessSimulation) -> tuple[EntityIdRegistry, dict[tuple[str, str | None], str]]:
    registry = EntityIdRegistry()
    observation = build_observation(simulation.manager, 0, registry)
    return registry, {(entity.kind, entity.team): entity.id for entity in observation.entities}


def test_research_and_cancel_share_the_existing_activity_queue() -> None:
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    manager.teams[TeamColor.BLUE].resources.update({"wood": 1000, "gold": 1000})
    registry, ids = _ids(simulation)
    translator = ActionTranslator(manager, registry)
    arsenal_id = ids[("Arsenal", "Blue")]

    assert translator.apply(ResearchAction(TeamColor.BLUE, arsenal_id, "aegis_knight_bulwark")) == 1
    observation = build_observation(manager, 0, registry)
    arsenal = next(entity for entity in observation.entities if entity.id == arsenal_id)
    blue = next(team for team in observation.teams if team.team == "Blue")
    assert arsenal.activity_queue[0].kind == "research"
    assert arsenal.activity_queue[0].content_id == "aegis_knight_bulwark"
    assert blue.faction_id == "AEGIS"
    assert blue.reserved_upgrades == ("aegis_knight_bulwark",)

    assert translator.apply(CancelActivityAction(TeamColor.BLUE, arsenal_id)) == 1
    assert not manager.production.queue_for(manager.state.buildings_for_team(TeamColor.BLUE)[1])
    assert manager.teams[TeamColor.BLUE].reserved_upgrades == []
    simulation.close()


def test_rally_supports_resource_enemy_and_ground_targets() -> None:
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    registry = EntityIdRegistry()
    observation = build_observation(manager, 0, registry)
    base_id = next(entity.id for entity in observation.entities if entity.kind == "Base" and entity.team == "Blue")
    wood_id = next(entity.id for entity in observation.entities if entity.kind == "Wood")
    enemy_id = next(entity.id for entity in observation.entities if entity.kind == "Base" and entity.team == "Red")
    translator = ActionTranslator(manager, registry)
    base = manager.bases_for_team(TeamColor.BLUE)[0]

    assert translator.apply(SetRallyAction(TeamColor.BLUE, base_id, target_id=wood_id)) == 1
    assert base.rally_order is not None
    assert base.rally_order.kind == "gather"
    assert translator.apply(SetRallyAction(TeamColor.BLUE, base_id, target_id=enemy_id)) == 1
    assert base.rally_order is not None
    assert base.rally_order.kind == "attack_move"
    assert translator.apply(SetRallyAction(TeamColor.BLUE, base_id, destination=(150, 150))) == 1
    assert base.rally_order is not None
    assert base.rally_order.kind == "move"
    simulation.close()


def test_repair_and_assist_construction_accept_explicit_peasants() -> None:
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    registry = EntityIdRegistry()
    observation = build_observation(manager, 0, registry)
    peasant_ids = tuple(
        entity.id for entity in observation.entities if entity.kind == "Peasant" and entity.team == "Blue"
    )
    base_id = next(entity.id for entity in observation.entities if entity.kind == "Base" and entity.team == "Blue")
    base = manager.bases_for_team(TeamColor.BLUE)[0]
    base.life -= 20
    translator = ActionTranslator(manager, registry)

    repair = RepairAction(TeamColor.BLUE, base_id, unit_ids=(peasant_ids[0],))
    assert translator.validate(repair) == (True, None)
    assert translator.apply(repair) == 1

    manager.teams[TeamColor.BLUE].resources["wood"] = 100
    builder = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
    assert manager.construct_building(builder, "house", (120, 170))
    updated = build_observation(manager, 0, registry)
    house_id = next(entity.id for entity in updated.entities if entity.kind == "House")
    assist = AssistConstructionAction(TeamColor.BLUE, house_id, unit_ids=(peasant_ids[1],), queue=True)
    assert translator.validate(assist) == (True, None)
    assert translator.apply(assist) == 1
    simulation.close()


def test_action_mask_uses_registry_roster_and_exposes_strategic_families() -> None:
    env = RtsNanoEnv(settings=_settings())
    manager = env._require_simulation().manager
    manager.teams[TeamColor.BLUE].resources.update({"wood": 1000, "gold": 1000})

    specs = env.action_mask(TeamColor.BLUE)
    unit_ids = {spec.unit_type for spec in specs if spec.kind == "build"}
    kinds = {spec.kind for spec in specs}

    assert unit_ids == set(CONTENT.units)
    assert {"research", "set_rally", "repair", "assist_construction", "cancel_activity"} <= kinds
    env.close()


def test_joint_research_reserves_exclusive_choice_before_mutation() -> None:
    env = RtsNanoEnv(settings=_settings())
    manager = env._require_simulation().manager
    manager.teams[TeamColor.BLUE].resources.update({"wood": 1000, "gold": 1000})
    observation = env.observe()
    arsenal_id = next(entity.id for entity in observation.entities if entity.kind == "Arsenal")

    result = env.step_joint(
        {
            TeamColor.BLUE: (
                ResearchAction(TeamColor.BLUE, arsenal_id, "aegis_knight_bulwark"),
                ResearchAction(TeamColor.BLUE, arsenal_id, "aegis_knight_vanguard"),
            )
        }
    )

    assert result.action_outcomes[0].accepted is True
    assert result.action_outcomes[1].accepted is False
    assert result.action_outcomes[1].reason == "exclusive_choice_reserved"
    assert [
        item.content_id for item in manager.production.queue_for(manager.state.buildings_for_team(TeamColor.BLUE)[1])
    ] == ["aegis_knight_bulwark"]
    env.close()
