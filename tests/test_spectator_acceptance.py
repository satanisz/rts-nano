"""Observer interaction and rendered frames cannot alter two-bot gameplay."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pygame

from rts_nano.application import GameSession, MatchController, MatchMode
from rts_nano.game.observations import EntityIdRegistry, Observation, build_observation
from rts_nano.game.ui.input_controller import InputController
from rts_nano.game.ui.match_view import MatchView
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.game.ui.state import PresentationState
from rts_nano.map_schema import load_map_settings


def _gameplay_snapshot(game: GameSession) -> Observation:
    snapshot = build_observation(game, game.state.tick_count, EntityIdRegistry())
    return replace(
        snapshot,
        current_team="observer",
        entities=tuple(replace(entity, selected=False) for entity in snapshot.entities),
    )


def test_observer_camera_inspection_and_rendering_preserve_real_two_bot_decisions() -> None:
    settings = load_map_settings(Path("src/rts_nano/maps/map_spec_01.json"))
    observed = MatchController(GameSession(settings), MatchMode.SPECTATE)
    headless = MatchController(GameSession(settings), MatchMode.SPECTATE)
    state = PresentationState(view=MatchView(MatchMode.SPECTATE))
    controller = InputController(state)
    renderer = GameRenderer(presentation=state)
    observed.session.set_viewport_size(1280, 720)
    screen = pygame.Surface((1280, 720))
    for tick in range(4000):
        observed.step()
        headless.step()
        if tick % 60 == 0:
            controller.handle_event(observed.session, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_TAB, mod=0))
            observed.session.camera_x = tick % 300
            observed.session.camera_y = tick % 400
            controller.handle_event(
                observed.session, pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(400, 200))
            )
            controller.handle_event(
                observed.session, pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(600, 300))
            )
            renderer.draw(screen, observed.session)
        if tick % 1000 == 0:
            assert _gameplay_snapshot(observed.session) == _gameplay_snapshot(headless.session)

    assert _gameplay_snapshot(observed.session) == _gameplay_snapshot(headless.session)
    for observed_bot, headless_bot in zip(observed._bots, headless._bots, strict=True):
        assert observed_bot._frame == headless_bot._frame
        assert observed_bot._vision.grid == headless_bot._vision.grid
        assert observed_bot.known_enemy_base_position == headless_bot.known_enemy_base_position
