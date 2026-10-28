"""Tests for terminal match presentation and restart input."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame
import pytest

from rts_nano.application import GameSession
from rts_nano.game.ui.input_controller import RESTART_MATCH_EVENT, InputController
from rts_nano.game.ui.match_result import match_result_buttons, match_result_title
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {"faction_id": "AEGIS", "peasant": [], "base": [[60, 60]]},
        "Red": {"faction_id": "RUST", "peasant": [], "base": [[250, 250]]},
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


def test_match_result_title_uses_current_player_perspective() -> None:
    manager = GameSession(_settings())
    manager.game_over_message = "Team Blue wins"
    assert match_result_title(manager) == "VICTORY"

    manager.current_team = TeamColor.RED
    assert match_result_title(manager) == "DEFEAT"

    manager.game_over_message = "Draw"
    assert match_result_title(manager) == "DRAW"


def test_restart_key_and_result_buttons_post_application_events(monkeypatch: pytest.MonkeyPatch) -> None:
    manager = GameSession(_settings())
    manager.game_over_message = "Team Blue wins"
    manager.paused = True
    posted: list[pygame.event.Event] = []
    monkeypatch.setattr(pygame.event, "post", posted.append)
    controller = InputController()

    controller.handle_event(manager, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r, mod=0))
    restart_rect = match_result_buttons(manager.screen_width, manager.screen_height)[0][1]
    controller.handle_event(
        manager,
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=restart_rect.center),
    )
    quit_rect = match_result_buttons(manager.screen_width, manager.screen_height)[1][1]
    controller.handle_event(
        manager,
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=quit_rect.center),
    )

    assert [event.type for event in posted] == [RESTART_MATCH_EVENT, RESTART_MATCH_EVENT, pygame.QUIT]


def test_result_overlay_renders_and_match_reset_retains_asset_cache() -> None:
    manager = GameSession(_settings())
    manager.game_over_message = "Team Blue wins"
    manager.paused = True
    screen = pygame.Surface((manager.screen_width, manager.screen_height))
    renderer = GameRenderer()
    assets = renderer.assets

    renderer.draw(screen, manager)
    renderer.reset_match()

    assert renderer.assets is assets


def test_result_overlay_does_not_have_a_second_pause_label_underneath() -> None:
    manager = GameSession(_settings())
    manager.game_over_message = "Draw"
    manager.state.match_end_reason = "time_limit"
    renderer = GameRenderer()
    paused_screen = pygame.Surface((manager.screen_width, manager.screen_height))
    unpaused_screen = paused_screen.copy()

    manager.paused = True
    renderer.draw(paused_screen, manager)
    manager.paused = False
    renderer.draw(unpaused_screen, manager)

    assert pygame.image.tobytes(paused_screen, "RGB") == pygame.image.tobytes(unpaused_screen, "RGB")


@pytest.mark.parametrize("overlay", ["tech_tree", "menu"])
def test_terminal_result_takes_precedence_over_open_overlays(overlay: str) -> None:
    manager = GameSession(_settings())
    manager.game_over_message = "Draw"
    manager.paused = True
    renderer = GameRenderer()
    baseline = pygame.Surface((manager.screen_width, manager.screen_height))
    with_overlay = baseline.copy()
    renderer.draw(baseline, manager)

    renderer.presentation.tech_tree_visible = overlay == "tech_tree"
    manager.menu_active = overlay == "menu"
    renderer.draw(with_overlay, manager)

    assert pygame.image.tobytes(baseline, "RGB") == pygame.image.tobytes(with_overlay, "RGB")
