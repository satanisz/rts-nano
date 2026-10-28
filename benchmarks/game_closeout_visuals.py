"""Render controlled C4 UI fixtures for inspection; these are not economy benchmarks.

Use SDL_VIDEODRIVER=dummy and SDL_AUDIODRIVER=dummy for a display-free run.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pygame

from rts_nano.application import GameSession
from rts_nano.game.ui.input_controller import RESTART_MATCH_EVENT, InputController
from rts_nano.game.ui.renderer import GameRenderer
from rts_nano.map_schema import load_map_settings
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.simulation.entities.base import Building
    from rts_nano.simulation.entities.units import Peasant


def _require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    """Save six actual 1280x720 renderer views using deterministic fixture setup."""
    pygame.init()
    pygame.display.set_mode((1, 1))
    output = Path("docs/reviews/assets/game-closeout-c4")
    output.mkdir(parents=True, exist_ok=True)
    game = GameSession(load_map_settings(Path("src/rts_nano/maps/map_spec_01.json")))
    game.set_viewport_size(1280, 720)
    game.camera_y = 690
    renderer = GameRenderer()
    controller = InputController(presentation=renderer.presentation)

    def save(name: str) -> None:
        screen = pygame.Surface((game.screen_width, game.screen_height))
        renderer.draw(screen, game)
        pygame.image.save(screen, output / f"{name}.png")

    def step(frames: int) -> None:
        for _ in range(frames):
            game.update()

    save("01-fog-start")
    # Fixed funding and the final-tick jump are visual fixture setup only.
    # The separate macro matrix earns its complete economy and advances every tick.
    game.teams[TeamColor.BLUE].resources.update(wood=3000, gold=3000)
    worker = cast("Peasant", game.state.entities_by_content_id("peasant", team=TeamColor.BLUE)[0])
    _require(game.construct_building(worker, "house", (380, 1050)), "House placement failed")
    house = cast("Building", game.state.entities_by_content_id("house", team=TeamColor.BLUE)[0])
    game.selected_entities = [house]
    step(100)
    save("02-construction")
    step(600)
    _require(not house.is_under_construction, "House did not complete")
    _require(game.construct_building(worker, "arsenal", (300, 1130)), "Arsenal placement failed")
    step(1000)
    _require(game.construct_building(worker, "spire", (220, 970)), "Spire placement failed")
    step(1000)
    spire = cast("Building", game.state.entities_by_content_id("spire", team=TeamColor.BLUE)[0])
    _require(game.produce_unit(spire, "mage"), "Mage queue failed")
    _require(game.research_upgrade(spire, "aegis_mage_arcbinder"), "Research queue failed")
    game.selected_entities = [spire]
    step(50)
    save("03-queue")
    controller.handle_event(game, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F9, mod=0))
    save("04-f9")
    # Keep F9 open: a terminal result must replace it and expose restart controls.
    game.state.tick_count = 35_999
    game.update()
    _require(game.game_over_message == "Draw", "Deadline did not produce a draw")
    save("05-result")
    controller.handle_event(game, pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r, mod=0))
    _require(any(event.type == RESTART_MATCH_EVENT for event in pygame.event.get()), "Restart input did not fire")
    game = game.restart()
    renderer.presentation.reset_match()
    renderer.reset_match()
    controller.reset_match()
    game.camera_y = 690
    save("06-restart")
    pygame.quit()
    print(f"Saved six fixture views to {output}")


if __name__ == "__main__":
    main()
