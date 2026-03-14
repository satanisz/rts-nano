from rts_nano.game.assets.entities.base_entities import Unit
from rts_nano.game.assets.entities.base_entities import Entity
from rts_nano.game.assets.entities import Peasant, Knight, Archer, Mage
from rts_nano.game.assets.entities import Wood, Cristal, TeamColor
from rts_nano.game.assets.entities import Base
from dataclasses import field
import pygame
from rts_nano.game.constants import *




class EntitiesGroup:
    def __init__(self, name: TeamColor):
        self.name: TeamColor = name
        self.resources: dict[str, int] = {"wood": 0, "cristal": 0}
        self.bases: list[Base] = []
        self.peasents: list[Peasant] = []
        self.knights: list[Knight] = []
        self.archers: list[Archer] = []
        self.mages: list[Mage] = []

    @property
    def all_entities(self) -> list[Entity]:
        all_ents: list[Entity] = []
        all_ents.extend(self.bases)
        all_ents.extend(self.peasents)
        all_ents.extend(self.knights)
        all_ents.extend(self.archers)
        all_ents.extend(self.mages)
        return all_ents

class ResourcesGroup:
    def __init__(self):
        self.cristals: list[Cristal] = []
        self.woods: list[Wood] = []




class GameManager:
    def __init__(self, map_settings: dict[str, dict[str, list[list[int]] | list[tuple[int, int]]]]):
        self.map_settings = map_settings  
        self.entities: dict[TeamColor, EntitiesGroup] = {}
        self.resources: ResourcesGroup = ResourcesGroup()
        self.selected_entities: list[Entity] = []
        self.current_team: TeamColor = TeamColor.BLUE
        # Drag selection state
        self.dragging: bool = False
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
        self.paused: bool = False
        
        self._load_map_settings()

    @property
    def all_entities(self) -> list[Entity]:
        ents = [entity for group in self.entities.values() for entity in group.all_entities]
        ents.extend(self.resources.woods)
        ents.extend(self.resources.cristals)
        return ents

    def _load_map_settings(self) -> None:
        for category_str, assets in self.map_settings.items():
            category = TeamColor(category_str)
            group = EntitiesGroup(category)
            self.entities[category] = group
            
            for asset_type, coords in assets.items():
                if asset_type == "peasent":
                    group.peasents.extend([Peasant(x, y, team=category) for x, y in coords])
                elif asset_type == "base":
                    group.bases.extend([Base(x, y, team=category) for x, y in coords])
                elif asset_type == "wood":
                    self.resources.woods.extend([Wood(x, y) for x, y in coords])
                elif asset_type == "cristal":
                    self.resources.cristals.extend([Cristal(x, y) for x, y in coords])

    def handle_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                if self.current_team == TeamColor.BLUE:
                    self.current_team = TeamColor.RED
                else:
                    self.current_team = TeamColor.BLUE
                for entity in self.selected_entities:
                    entity.selected = False
                self.selected_entities.clear()
            elif event.key == pygame.K_q:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            elif event.key == pygame.K_p:
                self.paused = not self.paused

        elif event.type == pygame.MOUSEBUTTONDOWN:
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
                    if isinstance(entity, Peasant):
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
                if isinstance(entity, Unit) and entity.team == self.current_team and entity.contains_point(self.drag_start):
                    entity.selected = True
                    self.selected_entities.append(entity)
                    break  # Only select one unit on click
        else:
            # Box selection - select all units within box
            for entity in self.all_entities:
                if isinstance(entity, Unit) and entity.team == self.current_team:
                    cx, cy = entity.get_center()
                    if min_x <= cx <= max_x and min_y <= cy <= max_y:
                        entity.selected = True
                        self.selected_entities.append(entity)


    def update(self):
        if self.paused:
            return
            
        all_ents = self.all_entities
        for entity in all_ents:
            if isinstance(entity, Unit):
                entity.update(all_ents)
                
                # Gathering Logic
                if entity.state == "GATHERING":
                    resource = entity.target_entity or entity.source_resource
                    if isinstance(resource, (Wood, Cristal)):
                        is_wood = isinstance(resource, Wood)
                        
                        if resource.amount > 0:
                            gathered = min(1, resource.amount)
                            resource.amount -= gathered
                            
                            if is_wood:
                                entity.carry_wood += gathered
                            else:
                                entity.carry_cristal += gathered
                            
                            if resource.amount <= 0:
                                # Remove depleted resource
                                if isinstance(resource, Wood) and resource in self.resources.woods:
                                    self.resources.woods.remove(resource)
                                elif isinstance(resource, Cristal) and resource in self.resources.cristals:
                                    self.resources.cristals.remove(resource)
                                
                                entity.source_resource = None
                                entity.target_entity = None
                                
                        carry_amount = entity.carry_wood if is_wood else entity.carry_cristal        
                        if carry_amount >= entity.max_carry or (resource and resource.amount <= 0):
                            if is_wood and entity.carry_wood > entity.max_carry:
                                entity.carry_wood = entity.max_carry
                            elif not is_wood and entity.carry_cristal > entity.max_carry:
                                entity.carry_cristal = entity.max_carry
                            
                            # Find nearest base for this team
                            team_group = self.entities.get(entity.team)
                            team_bases = team_group.bases if team_group else []
                            if team_bases:
                                nearest_base = min(team_bases, key=lambda b: (b.x - entity.x)**2 + (b.y - entity.y)**2)
                                entity.set_target(nearest_base.get_center(), nearest_base)
                            else:
                                entity.state = "IDLE"
                
                # Depositing Logic
                elif entity.state == "DEPOSITING":
                    team_group = self.entities.get(entity.team)
                    if team_group:
                        team_group.resources["wood"] += entity.carry_wood
                        team_group.resources["cristal"] += entity.carry_cristal
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
        team_group = self.entities.get(self.current_team)
        ui_color = BLUE if self.current_team == TeamColor.BLUE else RED
        
        if team_group:
            res = team_group.resources
            num_buildings = len(team_group.bases)
            # Sum up units, knights, archers, mages according to entities group
            num_units = len(team_group.peasents) + len(team_group.knights) + len(team_group.archers) + len(team_group.mages)
        else:
            res = {"wood": 0, "cristal": 0}
            num_buildings = 0
            num_units = 0
            
        text = font.render(
            f"Team {self.current_team.value} | Wood: {res['wood']}   Cristal: {res['cristal']} | "
            f"Buildings: {num_buildings}   Units: {num_units}", 
            True, ui_color
        )
            
        if self.paused:
            pause_text = font.render("- PAUSED -", True, WHITE)
            text_rect = pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(pause_text, text_rect)
            
        screen.blit(text, (10, 10))
