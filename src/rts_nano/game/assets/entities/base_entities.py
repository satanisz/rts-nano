import logging
import pygame
import math
from pathlib import Path
from enum import Enum
from rts_nano.game.constants import *

BASE_DIR = Path(__file__).resolve().parent.parent

class TeamColor(str, Enum):
    BLUE = "Blue"
    RED = "Red"
    GREY = "Grey"
    RESOURCES = "Resources"

class Entity:
    def __init__(self, x, y, color, size, radius, class_name):
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.radius = radius
        self.selected = False
        self.life = 0
        self.class_name = class_name
        self.image = None
        self.original_image = None
        
    @classmethod
    def get_team_color(cls, team: TeamColor) -> tuple[int, int, int]:
        if team == TeamColor.BLUE:
            return BLUE
        elif team == TeamColor.RED:
            return RED
        elif team == TeamColor.GREY or team == TeamColor.RESOURCES:
            return GRAY
        else:
            raise ValueError(f"Unknown team color: {team}")

    def load_image(self, image_path):
        if image_path:
            try:
                self.image = pygame.image.load(image_path)
                self.image = pygame.transform.scale(self.image, (int(self.size), int(self.size)))
                self.original_image = self.image
            except Exception as e:
                logging.warning(f"Could not load image {image_path}: {e}")
                self.image = None
                self.original_image = None

    def draw(self, screen):
        # Draw hitbox circle for visualization
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(self.radius + 2), 1)
        
        # Draw image if available, otherwise draw colored rect
        top_left_x = int(self.x - self.size / 2)
        top_left_y = int(self.y - self.size / 2)
        if self.image:
            screen.blit(self.image, (top_left_x, top_left_y))
        else:
            pygame.draw.rect(screen, self.color, (top_left_x, top_left_y, self.size, self.size))
        
        if self.selected:
            pygame.draw.rect(screen, WHITE, (top_left_x, top_left_y, self.size, self.size), 1)

    def contains_point(self, pos):
        px, py = pos
        return self.x - self.size / 2 <= px <= self.x + self.size / 2 and self.y - self.size / 2 <= py <= self.y + self.size / 2

    def get_center(self):
        return self.x, self.y


class Resource(Entity):
    def __init__(self, x: int, y: int, name: str = "Resource"):
        super().__init__(x, y, GRAY, RESOURCE_SIZE, RESOURCE_RADIUS, name)
        self.amount = 100

class Building(Entity):
    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE):
        color = Entity.get_team_color(team)
        super().__init__(x, y, color, BUILDING_SIZE, BUILDING_RADIUS, "Building")
        self.team = team
        self.max_life = 500
        self.life = 500

class Unit(Entity):
    def __init__(self, x: int, y: int, team: TeamColor, size: int, radius: float):
        color = Entity.get_team_color(team)
        
        super().__init__(x, y, color, size, radius, "Unit")
        self.team = team
        self.default_facing = "right" if team == TeamColor.BLUE else "left"
        self.facing = self.default_facing
        self.prev_x = float(x)
        self.target_x = x
        self.target_y = y
        self.speed = UNIT_SPEED
        self.target_entity = None
        self.source_resource = None # For continuous harvesting
        self.carry_wood = 0
        self.carry_cristal = 0
        self.max_carry = 10
        self.max_life = 0
        self.life = 0
        self.attack_damage = 0
        self.attack_range = 0
        self.attack_speed = 0
        self.state = "IDLE" # IDLE, MOVING, GATHERING, RETURNING, DEPOSITING

    def draw(self, screen):
        dx = self.x - self.prev_x
        # small margin to avoid flapping
        if dx > 0.1:
            self.facing = "right"
        elif dx < -0.1:
            self.facing = "left"
            
        if self.original_image is not None:
            if self.facing != self.default_facing:
                self.image = pygame.transform.flip(self.original_image, True, False)
            else:
                self.image = self.original_image
                
        self.prev_x = self.x
        
        super().draw(screen)

    def set_target(self, pos, target_entity=None):
        self.target_x, self.target_y = pos
        self.target_entity = target_entity
        
        # If we are manually setting a target, we might be interrupting a loop, so reset source_resource unless we are clicking on it?
        # For now, let's reset it if we set a new manual target that is NOT a resource.
        if isinstance(target_entity, Resource):
            self.source_resource = target_entity
        elif target_entity is None:
             self.source_resource = None

        self.state = "MOVING"



    def resolve_collisions(self, entities):
        my_cx, my_cy = self.get_center()
        
        for entity in entities:
            if entity is self:
                continue
                
            other_cx, other_cy = entity.get_center()
            dx = my_cx - other_cx
            dy = my_cy - other_cy
            dist = math.sqrt(dx**2 + dy**2)
            
            min_dist = self.radius + entity.radius
            
            if dist < min_dist and dist > 0:
                # Collision detected, push away
                overlap = min_dist - dist
                push_x = (dx / dist) * (overlap / 2)
                push_y = (dy / dist) * (overlap / 2)
                
                # Apply push
                self.x += push_x
                self.y += push_y
