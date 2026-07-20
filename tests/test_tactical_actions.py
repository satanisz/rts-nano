"""Tactical RL actions, queue parity, and action-facing Mage state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.action_translation import ActionTranslator
from rts_nano.actions import AttackAction, AttackMoveAction, CastAction, MoveAction, PatrolAction, ReturnCargoAction
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
            "base": [[40, 40]],
            "peasant": [[70, 60]],
            "mage": [[130, 150]],
            "knight": [[150, 180]],
        },
        "Red": {
            "faction_id": "RUST",
            "base": [[430, 260]],
            "mage": [[260, 150]],
            "knight": [[200, 150]],
        },
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 500,
            "height": 320,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def _translator(
    simulation: HeadlessSimulation,
) -> tuple[ActionTranslator, dict[tuple[str, str], str]]:
    registry = EntityIdRegistry()
    observation = build_observation(simulation.manager, 0, registry)
    ids = {(entity.kind, entity.team): entity.id for entity in observation.entities if entity.team is not None}
    return ActionTranslator(simulation.manager, registry), ids


def test_cast_action_supports_entity_and_ground_targets() -> None:
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_mage_arcbinder")
    assert manager.upgrades.complete(TeamColor.RED, "rust_mage_plaguecaller")
    translator, ids = _translator(simulation)
    red_knight = manager.state.entities_by_content_id("knight", team=TeamColor.RED)[0]
    blue_knight = manager.state.entities_by_content_id("knight", team=TeamColor.BLUE)[0]

    entity_cast = CastAction(
        TeamColor.BLUE,
        ids[("Mage", "Blue")],
        "arc_bind",
        target_id=ids[("Knight", "Red")],
    )
    assert translator.validate(entity_cast) == (True, None)
    assert translator.apply(entity_cast) == 1
    simulation.step(1)
    assert red_knight.arc_mark_remaining_frames > 0

    ground_cast = CastAction(
        TeamColor.RED,
        ids[("Mage", "Red")],
        "toxic_cloud",
        destination=blue_knight.get_center(),
    )
    assert translator.validate(ground_cast) == (True, None)
    assert translator.apply(ground_cast) == 1
    simulation.step(1)
    assert blue_knight.poison_remaining_frames > 0
    simulation.close()


def test_observation_and_mask_expose_unlocked_ability_state() -> None:
    env = RtsNanoEnv(settings=_settings())
    manager = env._require_simulation().manager
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_mage_arcbinder")

    observation = env.observe()
    mage = next(entity for entity in observation.entities if entity.kind == "Mage" and entity.team == "Blue")
    ability = mage.abilities[0]
    cast_spec = next(spec for spec in env.action_mask(TeamColor.BLUE) if spec.kind == "cast")

    assert observation.schema_version == 4
    assert mage.energy == mage.energy_max == 100
    assert ability.ability_id == "arc_bind"
    assert ability.target_kind == "enemy"
    assert ability.cooldown_remaining == 0
    assert ability.energy_ready is True
    assert cast_spec.ability_id == "arc_bind"
    assert cast_spec.caster_id == mage.id
    env.close()


def test_shift_queue_parity_covers_attack_move_patrol_and_target_attack() -> None:
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    translator, ids = _translator(simulation)
    knight_id = ids[("Knight", "Blue")]
    knight = manager.state.entities_by_content_id("knight", team=TeamColor.BLUE)[0]

    assert translator.apply(MoveAction(TeamColor.BLUE, (100, 220), (knight_id,))) == 1
    assert translator.apply(AttackMoveAction(TeamColor.BLUE, (250, 220), (knight_id,), queue=True)) == 1
    assert translator.apply(PatrolAction(TeamColor.BLUE, (180, 220), (knight_id,), queue=True)) == 1
    assert (
        translator.apply(
            AttackAction(
                TeamColor.BLUE,
                ids[("Knight", "Red")],
                (knight_id,),
                queue=True,
            )
        )
        == 1
    )

    assert knight.current_order is not None
    assert knight.current_order.kind == "move"
    assert [order.kind for order in knight.order_queue] == ["attack_move", "patrol", "attack"]
    knight.state = "IDLE"
    knight.path.clear()
    knight.target_entity = None
    manager.orders.update_queues()
    assert knight.current_order is not None
    assert knight.current_order.kind == "attack_move"
    assert [order.kind for order in knight.order_queue] == ["patrol", "attack"]
    simulation.close()


def test_return_cargo_can_be_queued_behind_movement() -> None:
    simulation = HeadlessSimulation.from_settings(_settings())
    manager = simulation.manager
    translator, ids = _translator(simulation)
    peasant_id = ids[("Peasant", "Blue")]
    peasant = manager.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0]
    peasant.carry_wood = 5

    assert translator.apply(MoveAction(TeamColor.BLUE, (120, 80), (peasant_id,))) == 1
    action = ReturnCargoAction(TeamColor.BLUE, unit_ids=(peasant_id,), queue=True)
    assert translator.apply(action) == 1
    assert [order.kind for order in peasant.order_queue] == ["return_cargo"]
    peasant.state = "IDLE"
    peasant.path.clear()
    peasant.target_entity = None
    manager.orders.update_queues()
    assert peasant.current_order is not None
    assert peasant.current_order.kind == "return_cargo"
    assert peasant.target_entity is manager.bases_for_team(TeamColor.BLUE)[0]
    simulation.close()


def test_locked_cast_is_an_independent_reported_noop() -> None:
    env = RtsNanoEnv(settings=_settings())
    observation = env.observe()
    mage_id = next(entity.id for entity in observation.entities if entity.kind == "Mage" and entity.team == "Blue")

    result = env.step_joint(
        {TeamColor.BLUE: (CastAction(TeamColor.BLUE, mage_id, "arc_bind", destination=(200, 150)),)}
    )

    assert result.action_outcomes[0].accepted is False
    assert result.action_outcomes[0].reason == "locked_ability"
    env.close()
