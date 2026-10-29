"""Render real spectator match states for visual acceptance with dummy SDL."""

from __future__ import annotations

from pathlib import Path

import pygame

from rts_nano.application import GameSession, MatchController, MatchMode
from rts_nano.game.ui.input_controller import RESTART_MATCH_EVENT, InputController
from rts_nano.game.ui.match_view import MatchView
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.game.ui.state import PresentationState
from rts_nano.map_schema import load_map_settings
from rts_nano.simulation.entities import TeamColor


def _require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    """Save observer views after earned bot development and a natural bounded result."""
    pygame.init()
    pygame.display.set_mode((1, 1))
    output = Path("docs/reviews/assets/bot-spectator")
    output.mkdir(parents=True, exist_ok=True)
    match = MatchController(
        GameSession(load_map_settings(Path("src/rts_nano/maps/map_spec_01.json"))), MatchMode.SPECTATE
    )
    game = match.session
    game.set_viewport_size(1280, 720)
    state = PresentationState(view=MatchView(MatchMode.SPECTATE))
    renderer = GameRenderer(presentation=state)
    controller = InputController(state)

    def key(code: int) -> None:
        controller.handle_event(game, pygame.event.Event(pygame.KEYDOWN, key=code, mod=0))

    def click(point: tuple[int, int]) -> None:
        controller.handle_event(game, pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=point))
        controller.handle_event(game, pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=point))

    def navigate(team: TeamColor) -> None:
        base = game.bases_for_team(team)[0]
        rect = game._minimap_rect()
        click(
            (
                rect.left + int(base.x * rect.width / game.map_width),
                rect.top + int(base.y * rect.height / game.map_height),
            )
        )

    def save(name: str) -> None:
        screen = pygame.Surface((game.screen_width, game.screen_height))
        renderer.draw(screen, game)
        pygame.image.save(screen, output / f"{name}.png")

    for _ in range(4000):
        match.step()
        state.view.refresh(game)
    navigate(TeamColor.BLUE)
    save("01-all")
    key(pygame.K_TAB)
    save("02-blue")
    key(pygame.K_TAB)
    navigate(TeamColor.RED)
    save("03-red")
    key(pygame.K_TAB)
    producer = game.production_buildings_for_team(TeamColor.RED)[-1]
    click(game._world_to_screen(producer.get_center()))
    _require(game.selected_entities == [producer], "Spectator inspection failed")
    save("04-inspection")
    key(pygame.K_TAB)
    key(pygame.K_TAB)
    key(pygame.K_F9)
    save("05-technology")
    key(pygame.K_ESCAPE)
    key(pygame.K_p)
    key(pygame.K_F10)
    options = state.view.menu_options(game)
    index = next(index for index, option in enumerate(options) if option.startswith("SPEED:"))
    top = (game.screen_height - (len(options) * 70 - 20)) // 2
    click((game.screen_width // 2, top + index * 70 + 25))
    save("06-menu-speed")
    key(pygame.K_F10)
    _require(game.paused, "Menu did not preserve the explicit pause")
    key(pygame.K_p)
    key(pygame.K_F9)
    for _ in range(36_000):
        match.step()
        if game.game_over_message is not None:
            break
    _require(game.game_over_message is not None, "Match did not end")
    save("07-result")
    pygame.event.clear()
    key(pygame.K_r)
    _require(any(event.type == RESTART_MATCH_EVENT for event in pygame.event.get()), "R did not request restart")
    match = match.restart()
    game = match.session
    state.reset_match()
    renderer.reset_match()
    controller.reset_match()
    navigate(TeamColor.BLUE)
    save("08-restart")
    game.set_viewport_size(640, 360)
    save("09-compact")
    pygame.quit()
    print(f"Saved nine earned-match observer views to {output}")


if __name__ == "__main__":
    main()
