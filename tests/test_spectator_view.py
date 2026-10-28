"""Spectator visibility and actual input must remain read-only for gameplay."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from rts_nano.application import GameSession, MatchController, MatchMode
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.game.ui.input_controller import FULLSCREEN_TOGGLE_EVENT, RESTART_MATCH_EVENT, InputController
from rts_nano.game.ui.match_result import match_result_title
from rts_nano.game.ui.match_view import MatchView
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.game.ui.state import PresentationState
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "base": [[80, 80]],
            "peasant": [[120, 120]],
            "mage": [[180, 120]],
            "arsenal": [[80, 200]],
            "spire": [[160, 200]],
        },
        "Red": {"faction_id": "RUST", "base": [[1450, 800]], "knight": [[1200, 300]]},
        "Resources": {"wood": [[1200, 500]], "gold": [[400, 200]]},
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


def _controls() -> tuple[GameSession, PresentationState, InputController]:
    game = GameSession(_settings())
    game.set_viewport_size(1280, 720)
    return game, (state := PresentationState(view=MatchView(MatchMode.SPECTATE))), InputController(state)


def _snapshot(game: GameSession) -> dict[str, object]:
    snapshot = build_observation(game, game.state.tick_count, EntityIdRegistry()).to_dict()
    snapshot.pop("current_team")
    for entity in snapshot["entities"]:
        entity.pop("selected")
    return snapshot


def _key(controller: InputController, game: GameSession, key: int, mod: int = 0) -> None:
    controller.handle_event(game, pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod))


def _click(controller: InputController, game: GameSession, point: tuple[int, int], button: int = 1) -> None:
    controller.handle_event(game, pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=point))
    controller.handle_event(game, pygame.event.Event(pygame.MOUSEBUTTONUP, button=button, pos=point))


@pytest.mark.parametrize("content_id", ["peasant", "base", "arsenal", "spire", "mage"])
def test_gameplay_hotkeys_cards_and_right_clicks_cannot_change_an_observed_world(content_id: str) -> None:
    game, state, controller = _controls()
    game.teams[TeamColor.BLUE].resources.update(wood=3000, gold=3000)
    selected = game.state.entities_by_content_id(content_id, team=TeamColor.BLUE)[0]
    game.selected_entities = [selected]
    worker = game.units_for_team(TeamColor.BLUE)[0]
    game.issue_move_order(TeamColor.BLUE, (450, 220), [worker])
    before = _snapshot(game)

    for key in (
        pygame.K_b,
        pygame.K_y,
        pygame.K_m,
        pygame.K_s,
        pygame.K_h,
        pygame.K_c,
        pygame.K_a,
        pygame.K_t,
        pygame.K_g,
        pygame.K_w,
        pygame.K_e,
        pygame.K_x,
        pygame.K_z,
        pygame.K_u,
        pygame.K_i,
    ):
        _key(controller, game, key)
    _key(controller, game, pygame.K_1, pygame.KMOD_CTRL)
    _key(controller, game, pygame.K_1)
    for rect in state.command_panel.slot_rects(game.screen_width, game.screen_height):
        _click(controller, game, rect.center)
    for point in ((450, 220), (1200, 300), (400, 200)):
        _click(controller, game, point, button=3)
    for button in state.command_panel.build(game, game.screen_width, game.screen_height):
        if button.enabled:
            controller._dispatch_command_button(game, button)

    assert _snapshot(game) == before
    assert game.pending_unit_command is None
    assert game.pending_construction_type is None
    assert not game.control_groups
    assert not state.click_markers


def test_all_view_inspects_both_sides_and_resources_without_issuing_orders() -> None:
    game, state, controller = _controls()
    before = _snapshot(game)
    for content_id, point in (("peasant", (120, 120)), ("knight", (1200, 300)), ("wood", (1200, 500))):
        _click(controller, game, point)
        assert str(game.selected_entities[0].content_id) == content_id
    assert state.view.fog_for(game) is None
    assert _snapshot(game) == before


def test_team_views_apply_visibility_to_inspection_and_cycle_back_to_all() -> None:
    game, state, controller = _controls()
    _key(controller, game, pygame.K_TAB)
    assert state.view.perspective == TeamColor.BLUE
    _click(controller, game, (1200, 300))
    assert not game.selected_entities
    _key(controller, game, pygame.K_TAB)
    assert state.view.perspective == TeamColor.RED
    _click(controller, game, (1200, 300))
    assert str(game.selected_entities[0].content_id) == "knight"
    _key(controller, game, pygame.K_TAB)
    assert state.view.perspective is None
    assert not game.selected_entities


def test_observer_exploration_accumulates_off_view_and_resets_without_revealing_the_world() -> None:
    game, state, _controller = _controls()
    worker = game.units_for_team(TeamColor.BLUE)[0]
    resource = game.state.resources_by_content("wood")[0]
    state.view.refresh(game)
    worker.x, worker.y = 1200, 500
    state.view.refresh(game)
    worker.x, worker.y = 120, 120
    state.view.refresh(game)
    state.view.cycle_perspective(game)
    assert state.view.can_inspect(game, resource)
    assert not state.view.can_inspect(game, game.state.entities_by_content_id("knight")[0])

    state.reset_match()
    state.view.refresh(game)
    state.view.cycle_perspective(game)
    assert not state.view.can_inspect(game, resource)


def test_full_map_view_and_team_switches_do_not_change_either_bots_knowledge() -> None:
    game, state, _controller = _controls()
    match = MatchController(game, MatchMode.SPECTATE)
    before = [[row[:] for row in bot._vision.grid] for bot in match._bots]
    for _ in range(4):
        state.view.refresh(game)
        state.view.cycle_perspective(game)
    assert [bot._vision.grid for bot in match._bots] == before
    assert all(bot.known_enemy_base_position is None for bot in match._bots)
    assert all(fog is not bot._vision for fog in state.view._fogs.values() for bot in match._bots)


def test_minimap_navigation_and_pause_menu_speed_f9_restart_controls_work() -> None:
    game, state, controller = _controls()
    game.camera_x = game.camera_y = 0
    minimap = game._minimap_rect()
    _click(controller, game, (minimap.right - 2, minimap.bottom - 2))
    assert game.camera_x > 0
    assert game.camera_y > 0
    assert not game.minimap_dragging
    _key(controller, game, pygame.K_SPACE)
    assert game.paused
    _key(controller, game, pygame.K_F10)
    assert game.menu_active
    assert game.paused
    options = state.view.menu_options(game)
    assert "SAVE" not in options
    assert "LOAD" not in options
    index = next(index for index, label in enumerate(options) if label.startswith("SPEED:"))
    top = (game.screen_height - (len(options) * 70 - 20)) // 2
    _click(controller, game, (game.screen_width // 2, top + index * 70 + 25))
    assert game.fps_multiplier == 2
    _key(controller, game, pygame.K_F10)
    assert not game.menu_active
    assert game.paused
    _key(controller, game, pygame.K_p)
    assert not game.paused
    _key(controller, game, pygame.K_F9)
    assert state.tech_tree_visible
    _key(controller, game, pygame.K_ESCAPE)
    assert not state.tech_tree_visible
    pygame.event.clear()
    _key(controller, game, pygame.K_r)
    _key(controller, game, pygame.K_F11)
    assert [event.type for event in pygame.event.get()] == [RESTART_MATCH_EVENT, FULLSCREEN_TOGGLE_EVENT]


@pytest.mark.parametrize(
    ("message", "label"), [("Team Blue wins", "BLUE WINS"), ("Team Red wins", "RED WINS"), ("Draw", "DRAW")]
)
def test_spectator_results_are_team_neutral(message: str, label: str) -> None:
    game, _state, _controller = _controls()
    game.game_over_message = message
    for team in (TeamColor.BLUE, TeamColor.RED):
        game.current_team = team
        assert match_result_title(game, spectator=True) == label


def test_world_and_minimap_render_the_same_observer_visibility_policy() -> None:
    game, state, controller = _controls()
    renderer = GameRenderer(presentation=state)
    screen = pygame.Surface((game.screen_width, game.screen_height))
    enemy = game.state.entities_by_content_id("knight")[0]
    renderer.draw(screen, game)
    world_pixel_all = screen.get_at((1200, 300))
    minimap = game._minimap_rect()
    marker = (
        minimap.left + int(enemy.x * minimap.width / game.map_width),
        minimap.top + int(enemy.y * minimap.height / game.map_height),
    )
    minimap_pixel_all = screen.get_at(marker)

    _key(controller, game, pygame.K_TAB)
    renderer.draw(screen, game)
    assert screen.get_at((1200, 300)) != world_pixel_all
    assert screen.get_at(marker) != minimap_pixel_all
    assert screen.get_at((1200, 300))[:3] == (0, 0, 0)
