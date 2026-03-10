import pygame
from rts_nano.game.constants import *
from rts_nano.game.entities import Unit, Resource, Building


    map_settings = {
        "blue": {
            "unit": [(100, 100), (150, 150)],
            "base": [(50, 250)],
            },
        "red": {
            "unit": [(700, 800)],
            "base": [(750, 850)]
            },
        "resources": {
            "wood": [(300, 300), (400, 200)],
            "cristal": [(350, 350)],
        "envirament" : [],
        }
    }



class GameManager:
    def __init__(self, map_settings):

        self.map_settings: dict = map_settings  
        self.entities = []
        self.selected_entities = []
        self.resources = 0
        # Drag selection state
        self.dragging = False
        self.drag_start = None
        self.drag_end = None



    def _load_mapp_settings(self)
        # Initial entities

        for type_asset in self.map_settings:
            for assets in type_asset:
                for asset in type_asset[assets]:

                    

        self.base = Building(50, 250)
        self.entities.append(self.base)
        self.entities.append(Unit(100, 100))
        self.entities.append(Unit(150, 100))
        self.entities.append(Resource(300, 300))
        self.entities.append(Resource(400, 200))

    def handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            
            if event.button == 1: # Left click - Start drag or single select
                self.dragging = True
                self.drag_start = mouse_pos
                self.drag_end = mouse_pos
            
            elif event.button == 3: # Right click - Move/Interact
                target_entity = None
                for entity in self.entities:
                    if entity.contains_point(mouse_pos):
                        target_entity = entity
                        break

                for entity in self.selected_entities:
                    if isinstance(entity, Unit):
                        entity.set_target(mouse_pos, target_entity)
        
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.dragging:
                self.dragging = False
                # Select units within drag box
                self.select_units_in_box()
                self.drag_start = None
                self.drag_end = None
        
        elif event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.drag_end = pygame.mouse.get_pos()
    
    def select_units_in_box(self):
        if not self.drag_start or not self.drag_end:
            return
        
        # Calculate selection box bounds
        x1, y1 = self.drag_start
        x2, y2 = self.drag_end
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)
        
        # Check if this is a click (small drag) or a drag (box selection)
        drag_distance = ((x2 - x1)**2 + (y2 - y1)**2) ** 0.5
        is_click = drag_distance < 5  # Threshold in pixels
        
        # Clear previous selection
        for entity in self.entities:
            entity.selected = False
        self.selected_entities.clear()
        
        if is_click:
            # Single-click selection - select one unit at click position
            for entity in self.entities:
                if isinstance(entity, Unit) and entity.contains_point(self.drag_start):
                    entity.selected = True
                    self.selected_entities.append(entity)
                    break  # Only select one unit on click
        else:
            # Box selection - select all units within box
            for entity in self.entities:
                if isinstance(entity, Unit):
                    cx, cy = entity.get_center()
                    if min_x <= cx <= max_x and min_y <= cy <= max_y:
                        entity.selected = True
                        self.selected_entities.append(entity)


    def update(self):
        for entity in self.entities:
            if isinstance(entity, Unit):
                entity.update(self.entities)
                
                # Gathering Logic
                if entity.state == "GATHERING":
                    entity.carry += 1
                    if entity.carry >= entity.max_carry:
                        entity.carry = entity.max_carry
                        # Return to base
                        entity.set_target(self.base.get_center(), self.base)
                
                # Depositing Logic
                elif entity.state == "DEPOSITING":
                    self.resources += entity.carry
                    entity.carry = 0
                    # Return to source resource if it exists
                    if entity.source_resource and entity.source_resource in self.entities:
                         entity.set_target(entity.source_resource.get_center(), entity.source_resource)
                    else:
                        entity.state = "IDLE"
                        entity.source_resource = None

    def draw(self, screen):
        for entity in self.entities:
            entity.draw(screen)
        
        # Draw drag selection box
        if self.dragging and self.drag_start and self.drag_end:
            x1, y1 = self.drag_start
            x2, y2 = self.drag_end
            min_x = min(x1, x2)
            max_x = max(x1, x2)
            min_y = min(y1, y2)
            max_y = max(y1, y2)
            width = max_x - min_x
            height = max_y - min_y
            # Draw semi-transparent box
            selection_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            selection_surface.fill((0, 255, 0, 50))  # Green with transparency
            screen.blit(selection_surface, (min_x, min_y))
            # Draw border
            pygame.draw.rect(screen, GREEN, (min_x, min_y, width, height), 2)
        
        # Draw resource count
        font = pygame.font.SysFont(None, 36)
        text = font.render(f"Resources: {self.resources}", True, WHITE)
        screen.blit(text, (10, 10))
