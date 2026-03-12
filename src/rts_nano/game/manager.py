from dataclasses import field
import pygame
from rts_nano.game.constants import *
from rts_nano.game.entities import Unit, Resource, Building, Entity, Wood, Cristal, Knight, Archer, TeamColor



class Team:
    def __init__(self, name: str):
        self.name = name
        
        self.base: list[Building] = field(default_factory=list)
        self.units: list[Unit] = field(default_factory=list)
        self.knights: list[Knight] = field(default_factory=list)


class EnityGroup:
    def __init__(self, name: str):
        self.name = name
        self.entities: list[Entity] = []


class GameManager:
    def __init__(self, map_settings: dict[str, dict[str, list[list[int]] | list[tuple[int, int]]]]):
        self.map_settings = map_settings  
        self.entities: dict[TeamColor, list[Entity]] = {}
        self.selected_entities: list[Entity] = []
        self.resources: dict[str, int] = {"wood": 0, "cristal": 0}
        # Drag selection state
        self.dragging: bool = False
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
        
        self._load_map_settings()

    @property
    def all_entities(self) -> list[Entity]:
        return [entity for group in self.entities.values() for entity in group]

    def _load_map_settings(self) -> None:
        for category_str, assets in self.map_settings.items():
            category = TeamColor(category_str)
            self.entities[category] = []
            for asset_type, coords in assets.items():
                for x, y in coords:
                    if asset_type == "unit":
                        entity: Entity = Unit(x, y, team=category)
                    elif asset_type == "base":
                        entity = Building(x, y, team=category)
                    elif asset_type == "wood":
                        entity = Wood(x, y)
                    elif asset_type == "cristal":
                        entity = Cristal(x, y)
                    else:
                        continue
                    self.entities[category].append(entity)

    def handle_input(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            
            if event.button == 1: # Left click - Start drag or single select
                self.dragging = True
                self.drag_start = mouse_pos
                self.drag_end = mouse_pos
            
            elif event.button == 3: # Right click - Move/Interact
                target_entity = None
                for entity in self.all_entities:
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
        for entity in self.all_entities:
            entity.selected = False
        self.selected_entities.clear()
        
        if is_click:
            # Single-click selection - select one unit at click position
            for entity in self.all_entities:
                if isinstance(entity, Unit) and entity.contains_point(self.drag_start):
                    entity.selected = True
                    self.selected_entities.append(entity)
                    break  # Only select one unit on click
        else:
            # Box selection - select all units within box
            for entity in self.all_entities:
                if isinstance(entity, Unit):
                    cx, cy = entity.get_center()
                    if min_x <= cx <= max_x and min_y <= cy <= max_y:
                        entity.selected = True
                        self.selected_entities.append(entity)


    def update(self):
        all_ents = self.all_entities
        for entity in all_ents:
            if isinstance(entity, Unit):
                entity.update(all_ents)
                
                # Gathering Logic
                if entity.state == "GATHERING":
                    resource = entity.target_entity or entity.source_resource
                    if isinstance(resource, Wood):
                        if resource.amount > 0:
                            gathered = 1 if resource.amount >= 1 else resource.amount
                            resource.amount -= gathered
                            entity.carry_wood += gathered
                            
                            if resource.amount <= 0:
                                # Remove resource from game
                                if resource in self.entities.get(TeamColor.RESOURCES, []):
                                    self.entities[TeamColor.RESOURCES].remove(resource)
                                # Tell unit to find a new resource or go idle? Let's just have them deposit and go idle for now
                                entity.source_resource = None
                                entity.target_entity = None
                                
                        if entity.carry_wood >= entity.max_carry or (resource and resource.amount <= 0):
                            if entity.carry_wood >= entity.max_carry:
                                entity.carry_wood = entity.max_carry
                            # Find nearest base for this team
                            team_bases = [b for b in self.entities.get(entity.team, []) if isinstance(b, Building)]
                            if team_bases:
                                nearest_base = min(team_bases, key=lambda b: (b.x - entity.x)**2 + (b.y - entity.y)**2)
                                entity.set_target(nearest_base.get_center(), nearest_base)
                            else:
                                entity.state = "IDLE"
                    elif isinstance(resource, Cristal):
                        if resource.amount > 0:
                            gathered = 1 if resource.amount >= 1 else resource.amount
                            resource.amount -= gathered
                            entity.carry_cristal += gathered
                            
                            if resource.amount <= 0:
                                # Remove resource from game
                                if resource in self.entities.get(TeamColor.RESOURCES, []):
                                    self.entities[TeamColor.RESOURCES].remove(resource)
                                entity.source_resource = None
                                entity.target_entity = None
                                
                        if entity.carry_cristal >= entity.max_carry or (resource and resource.amount <= 0):
                            if entity.carry_cristal >= entity.max_carry:
                                entity.carry_cristal = entity.max_carry
                            # Find nearest base for this team
                            team_bases = [b for b in self.entities.get(entity.team, []) if isinstance(b, Building)]
                            if team_bases:
                                nearest_base = min(team_bases, key=lambda b: (b.x - entity.x)**2 + (b.y - entity.y)**2)
                                entity.set_target(nearest_base.get_center(), nearest_base)
                            else:
                                entity.state = "IDLE"
                
                # Depositing Logic
                elif entity.state == "DEPOSITING":
                    self.resources["wood"] += entity.carry_wood
                    self.resources["cristal"] += entity.carry_cristal
                    entity.carry_wood = 0
                    entity.carry_cristal = 0
                    # Return to source resource if it exists
                    if entity.source_resource and entity.source_resource in all_ents:
                         entity.set_target(entity.source_resource.get_center(), entity.source_resource)
                    else:
                        entity.state = "IDLE"
                        entity.source_resource = None

    def draw(self, screen):
        for entity in self.all_entities:
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
        text = font.render(f"Wood: {self.resources['wood']}   Cristal: {self.resources['cristal']}", True, WHITE)
        screen.blit(text, (10, 10))
