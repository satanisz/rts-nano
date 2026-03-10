import pygame
import sys
from rts_nano.game.constants import *
from rts_nano.game.manager import GameManager

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Simple RTS")
    clock = pygame.time.Clock()
    

    map_settings = {
        "Blue": {
            "unit": [(100, 100), (150, 150)],
            "base": [(50, 250)],
            },
        "Red": {
            "unit": [(700, 800)],
            "base": [(750, 850)]
            },
        "Resources": {
            "wood": [(300, 300), (400, 200)],
            "cristal": [(350, 350)]
        }
    }


    game_manager = GameManager(map_settings)

    running = True
    while running:
        # Event handling
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            game_manager.handle_input(event)

        # Update
        game_manager.update()

        # Draw
        screen.fill(BLACK)
        game_manager.draw(screen)
        
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
