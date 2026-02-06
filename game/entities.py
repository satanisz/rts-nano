import pygame
import math
from game.constants import *

class Entity:
    def __init__(self, x, y, color, size):
        self.x = x
        self.y = y
        self.color = color
        self.size = size
        self.selected = False

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.size, self.size))
        if self.selected:
            pygame.draw.rect(screen, WHITE, (self.x, self.y, self.size, self.size), 2)

    def contains_point(self, pos):
        px, py = pos
        return self.x <= px <= self.x + self.size and self.y <= py <= self.y + self.size

class Unit(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, BLUE, UNIT_SIZE)
        self.target_x = x
        self.target_y = y
        self.speed = UNIT_SPEED
        self.target_entity = None
        self.carry = 0
        self.max_carry = 10
        self.state = "IDLE" # IDLE, MOVING, GATHERING, RETURNING

    def set_target(self, pos, target_entity=None):
        self.target_x, self.target_y = pos
        self.target_entity = target_entity
        self.state = "MOVING"

    def update(self):
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

class Resource(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, YELLOW, RESOURCE_SIZE)
        self.amount = 100

class Building(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, RED, 40)
