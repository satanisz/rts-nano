"""Application entry point for the RTS Nano game."""

import json
import sys
from pathlib import Path

import pygame

from rts_nano.game.constants import FPS, GRAY, SCREEN_HEIGHT, SCREEN_WIDTH
from rts_nano.game.manager import GameManager

BASE_DIR = Path(__file__).resolve().parent

def main() -> None:
    """Run the game loop and load the default map configuration."""
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Simple RTS")
    clock = pygame.time.Clock()

    settings_path = BASE_DIR / "maps" / "map_settings_01.json"
    with open(settings_path, encoding="utf-8") as f:
        map_settings = json.load(f)

    game_manager = GameManager(map_settings)

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game_manager.handle_input(event)

        game_manager.update()

        screen.fill(GRAY)
        game_manager.draw(screen)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
