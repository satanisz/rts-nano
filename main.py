import pygame
import sys
from game.constants import *
from game.manager import GameManager

def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Simple RTS")
    clock = pygame.time.Clock()
    
    game_manager = GameManager()

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
