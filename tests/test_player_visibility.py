"""C2 player-input acceptance for fog-aware selection and object targeting."""

from __future__ import annotations

import pygame
import pytest

from rts_nano.application import GameSession
from rts_nano.game.ui.input_controller import InputController
from rts_nano.simulation.entities import TeamColor


def _session(visibility: str) -> GameSession:
    game = GameSession(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[80, 80]], "peasant": [[120, 120]], "mage": [[180, 120]]},
            "Red": {"faction_id": "RUST", "base": [[1450, 800]], "knight": [[1200, 300]]},
            "Resources": {"wood": [[1200, 450]], "gold": []},
            "Terrain": {
                "width": 1600,
                "height": 900,
                "water": [],
                "rocks": [],
                "ramps": [],
                "high_ground": [],
                "grass": [],
            },
        }
    )
    game.set_viewport_size(1600, 900)
    worker = game.state.entities_by_content_id("peasant")[0]
    if visibility != "unexplored":
        worker.x, worker.y = 1200, 380
        game.refresh_player_visibility()
        if visibility == "explored":
            worker.x, worker.y = 120, 120
    game.refresh_player_visibility()
    assert game.fog.is_visible(1200, 300) == (visibility == "visible")
    assert game.fog.is_explored(1200, 450) == (visibility != "unexplored")
    return game


def _click(controller: InputController, game: GameSession, position: tuple[int, int], button: int = 1) -> None:
    controller.handle_event(game, pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=position))
    controller.handle_event(game, pygame.event.Event(pygame.MOUSEBUTTONUP, button=button, pos=position))


def _command(controller: InputController, game: GameSession, action: str) -> None:
    button = next(
        item
        for item in controller.presentation.command_panel.build(game, game.screen_width, game.screen_height)
        if item.action == action
    )
    assert button.enabled
    _click(controller, game, button.rect.center)


@pytest.mark.parametrize("visibility", ["visible", "explored", "unexplored"])
@pytest.mark.parametrize("resource", [False, True])
def test_left_click_selection_uses_the_shared_visibility_rule(visibility: str, resource: bool) -> None:
    game = _session(visibility)
    target = game.state.resources_by_content("wood")[0] if resource else game.state.entities_by_content_id("knight")[0]
    _click(InputController(), game, tuple(map(int, target.get_center())))
    allowed = visibility != "unexplored" if resource else visibility == "visible"
    assert (target in game.selected_entities) == allowed


@pytest.mark.parametrize("visibility", ["visible", "explored", "unexplored"])
@pytest.mark.parametrize("resource", [False, True])
def test_right_click_does_not_disclose_hidden_targets(visibility: str, resource: bool) -> None:
    game = _session(visibility)
    target = game.state.resources_by_content("wood")[0] if resource else game.state.entities_by_content_id("knight")[0]
    worker = game.state.entities_by_content_id("peasant")[0]
    game.selected_entities = [worker]
    _click(InputController(), game, tuple(map(int, target.get_center())), 3)
    allowed = visibility != "unexplored" if resource else visibility == "visible"
    assert (worker.target_entity is target) == allowed
    assert worker.current_order is not None
    if not allowed:
        assert worker.current_order.kind == "move"
        assert worker.current_order.target_entity_id is None


@pytest.mark.parametrize("visibility", ["visible", "explored", "unexplored"])
@pytest.mark.parametrize("hotkey", [False, True])
def test_gather_card_and_hotkey_require_an_explored_resource(visibility: str, hotkey: bool) -> None:
    game = _session(visibility)
    worker = game.state.entities_by_content_id("peasant")[0]
    game.selected_entities = [worker]
    controller = InputController()
    if hotkey:
        controller.handle_event(game, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_g, mod=0))
    else:
        _command(controller, game, "gather")
    _click(controller, game, (1200, 450))
    assert (worker.target_entity is game.state.resources_by_content("wood")[0]) == (visibility != "unexplored")
    if visibility == "unexplored":
        assert game.menu_status == "Choose resource"


@pytest.mark.parametrize("visibility", ["visible", "explored", "unexplored"])
@pytest.mark.parametrize("resource", [False, True])
def test_rally_uses_ground_for_unknown_objects(visibility: str, resource: bool) -> None:
    game = _session(visibility)
    base = game.bases_for_team(TeamColor.BLUE)[0]
    game.selected_entities = [base]
    _click(InputController(), game, (1200, 450 if resource else 300), 3)
    assert base.rally_order is not None
    if resource and visibility != "unexplored":
        assert base.rally_order.kind == "gather"
        assert base.rally_order.target_entity_id is not None
    else:
        expected = "attack_move" if not resource and visibility == "visible" else "move"
        assert base.rally_order.kind == expected
        assert base.rally_order.target_entity_id is None


@pytest.mark.parametrize("visibility", ["visible", "explored", "unexplored"])
def test_entity_cast_card_requires_visible_enemy(visibility: str) -> None:
    game = _session(visibility)
    assert game.upgrades.complete(TeamColor.BLUE, "aegis_mage_arcbinder")
    caster = game.state.entities_by_content_id("mage")[0]
    game.selected_entities = [caster]
    controller = InputController()
    _command(controller, game, "cast")
    _click(controller, game, (1200, 300))
    if visibility == "visible":
        assert caster.current_order is not None
        assert caster.current_order.kind == "cast"
        assert caster.current_order.target_entity_id == game.state.entities_by_content_id("knight")[0].entity_id
    else:
        assert caster.current_order is None
    assert caster.energy == caster.energy_max
    assert not caster.ability_cooldowns


def test_sight_loss_keeps_legal_attack_but_prevents_new_selection_until_rediscovery() -> None:
    game = _session("visible")
    controller = InputController()
    worker = game.state.entities_by_content_id("peasant")[0]
    target = game.state.entities_by_content_id("knight")[0]
    game.selected_entities = [worker]
    _click(controller, game, (1200, 300), 3)
    worker.x, worker.y = 120, 120
    game.refresh_player_visibility()
    assert worker.target_entity is target  # Existing legal tracking remains the game rule.
    _click(controller, game, (1200, 300))
    assert game.selected_entities == []
    worker.x, worker.y = 1200, 380
    _click(controller, game, (1200, 300))
    assert game.selected_entities == [target]


def test_team_switch_and_restart_do_not_leak_exploration_or_live_selection() -> None:
    game = _session("visible")
    worker = game.state.entities_by_content_id("peasant")[0]
    worker.x, worker.y = 120, 120
    game.current_team = TeamColor.RED
    assert not game.fog.is_explored(80, 80)
    game.current_team = TeamColor.BLUE
    assert game.fog.is_explored(1200, 450)
    assert not game.fog.is_visible(1200, 450)
    restarted = game.restart()
    restarted.refresh_player_visibility()
    assert not restarted.fog.is_explored(1200, 450)
    assert not restarted.selected_entities


def test_selected_enemy_is_cleared_when_vision_is_lost() -> None:
    game = _session("visible")
    target = game.state.entities_by_content_id("knight")[0]
    game.selected_entities = [target]
    worker = game.state.entities_by_content_id("peasant")[0]
    worker.x, worker.y = 120, 120
    game.refresh_player_visibility()
    assert game.selected_entities == []
