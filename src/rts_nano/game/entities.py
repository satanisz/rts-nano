import logging
import pygame
import math
from pathlib import Path
from rts_nano.game.constants import *

BASE_DIR = Path(__file__).resolve().parent.parent

class Entity:
    def __init__(self, x, y, color, size, class_name, image_path=None):
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.radius = size / 4 if class_name == "Building" else size / 3 # Assume circular for collision
        self.selected = False
        self.class_name = class_name
        
        # Load image if provided
        self.image = None
        if image_path:
            try:
                self.image = pygame.image.load(image_path)
                self.image = pygame.transform.scale(self.image, (int(size), int(size)))
            except Exception as e:
                logging.warning(f"Could not load image {image_path}: {e}")
                self.image = None

    def draw(self, screen):
        # Draw hitbox circle for visualization (optional but requested "surroundings")
        pygame.draw.circle(screen, (50, 50, 50), (int(self.x + self.size/2), int(self.y + self.size/2)), int(self.radius + 2), 1)
        
        # Draw image if available, otherwise draw colored rect
        if self.image:
            screen.blit(self.image, (int(self.x), int(self.y)))
        else:
            pygame.draw.rect(screen, self.color, (self.x, self.y, self.size, self.size))
        
        if self.selected:
            pygame.draw.rect(screen, WHITE, (self.x, self.y, self.size, self.size), 2)

    def contains_point(self, pos):
        px, py = pos
        return self.x <= px <= self.x + self.size and self.y <= py <= self.y + self.size

    def get_center(self):
        return self.x + self.size / 2, self.y + self.size / 2

class Unit(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, BLUE, UNIT_SIZE, "Unit", str(BASE_DIR / "assets" / "blue_unit.png"))
        self.target_x = x
        self.target_y = y
        self.speed = UNIT_SPEED
        self.target_entity = None
        self.source_resource = None # For continuous harvesting
        self.carry = 0
        self.max_carry = 10
        self.state = "IDLE" # IDLE, MOVING, GATHERING, RETURNING, DEPOSITING

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

    def update(self, entities):
        # Movement Logic
        if self.state == "MOVING":
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = math.sqrt(dx**2 + dy**2)

            if dist < self.speed:
                self.x = self.target_x
                self.y = self.target_y
                if self.target_entity:
                    if isinstance(self.target_entity, Resource):
                        self.state = "GATHERING"
                    elif isinstance(self.target_entity, Building): # Base
                        self.state = "DEPOSITING"
                else:
                    self.state = "IDLE"
            else:
                self.x += (dx / dist) * self.speed
                self.y += (dy / dist) * self.speed
        
        # Collision Avoidance
        self.resolve_collisions(entities)

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
                
                # Update target if we are being pushed significantly? Maybe not needed for simple logic.

class Resource(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, YELLOW, RESOURCE_SIZE, "Resource", str(BASE_DIR / "assets" / "cristal.png"))
        self.amount = 100

class Building(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, RED, 40, "Building", str(BASE_DIR / "assets" / "blue_base.png"))
