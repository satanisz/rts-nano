import pygame
from game.constants import *
from game.entities import Unit, Resource, Building

class GameManager:
    def __init__(self):
        self.entities = []
        self.selected_entities = []
        self.resources = 0
        # Initial entities
        self.base = Building(50, 250)
        self.entities.append(self.base)
        self.entities.append(Unit(100, 100))
        self.entities.append(Unit(150, 100))
        self.entities.append(Resource(300, 300))
        self.entities.append(Resource(400, 200))

    def handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            
            if event.button == 1: # Left click - Select
                self.selected_entities.clear()
                for entity in self.entities:
                    if isinstance(entity, Unit) and entity.contains_point(mouse_pos):
                        entity.selected = True
                        self.selected_entities.append(entity)
                    else:
                        entity.selected = False
            
            elif event.button == 3: # Right click - Move/Interact
                target_entity = None
                for entity in self.entities:
                    if entity.contains_point(mouse_pos):
                        target_entity = entity
                        break

                for entity in self.selected_entities:
                    if isinstance(entity, Unit):
                        entity.set_target(mouse_pos, target_entity)

    def update(self):
        for entity in self.entities:
            if isinstance(entity, Unit):
                entity.update()
                
                # Gathering Logic
                if entity.state == "GATHERING":
                    entity.carry += 1
                    if entity.carry >= entity.max_carry:
                        entity.carry = entity.max_carry
                        # Return to base
                        entity.set_target((self.base.x, self.base.y), self.base)
                
                # Depositing Logic
                elif entity.state == "DEPOSITING":
                    self.resources += entity.carry
                    entity.carry = 0
                    # Return to resource
                    # We need to remember the resource. 
                    # For simplicity, if we were gathering from a resource, we go back to it.
                    # But unit.target_entity is currently the Base.
                    # We need to store the "source" resource.
                    # For now, let's just go idle to keep it simple or bounce back if we can.
                    entity.state = "IDLE" 
                    # To make it loop, we would need to store 'last_resource' in Unit.

    def draw(self, screen):
        for entity in self.entities:
            entity.draw(screen)
        
        # Draw resource count
        font = pygame.font.SysFont(None, 36)
        text = font.render(f"Resources: {self.resources}", True, WHITE)
        screen.blit(text, (10, 10))
