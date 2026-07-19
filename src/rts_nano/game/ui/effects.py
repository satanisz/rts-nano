"""Presentation-owned projectile effects driven by simulation events."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from rts_nano.game.constants import BLACK, CYAN, WHITE

if TYPE_CHECKING:
    from rts_nano.simulation.entities.base import Entity


@dataclass(slots=True)
class MagicMissile:
    """Cosmetic homing projectile for artillery attacks."""

    x: float
    y: float
    target_x: float
    target_y: float
    target_entity: Entity | None = None
    speed: float = 8.0
    radius: int = 5

    def update(self) -> bool:
        """Move the projectile and return False when it reaches the target."""
        if self.target_entity is not None and getattr(self.target_entity, "life", 1) > 0:
            self.target_x, self.target_y = self.target_entity.get_center()
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.hypot(dx, dy)
        if distance <= self.speed or distance == 0:
            self.x, self.y = self.target_x, self.target_y
            return False
        self.x += (dx / distance) * self.speed
        self.y += (dy / distance) * self.speed
        return True

    def draw(self, screen: pygame.Surface, offset: tuple[float, float]) -> None:
        """Draw a bright projectile core and glow."""
        draw_pos = (int(self.x - offset[0]), int(self.y - offset[1]))
        pygame.draw.circle(screen, (120, 235, 255), draw_pos, self.radius + 3)
        pygame.draw.circle(screen, CYAN, draw_pos, self.radius)
        pygame.draw.circle(screen, WHITE, draw_pos, 2)


@dataclass(slots=True)
class ArcherShot:
    """Cosmetic projectile for ordinary ranged attacks."""

    x: float
    y: float
    target_x: float
    target_y: float
    target_entity: Entity | None = None
    speed: float = 10.0
    radius: int = 3

    def update(self) -> bool:
        """Move the projectile and return False when it reaches the target."""
        if self.target_entity is not None and getattr(self.target_entity, "life", 1) > 0:
            self.target_x, self.target_y = self.target_entity.get_center()
        dx = self.target_x - self.x
        dy = self.target_y - self.y
        distance = math.hypot(dx, dy)
        if distance <= self.speed or distance == 0:
            self.x, self.y = self.target_x, self.target_y
            return False
        self.x += (dx / distance) * self.speed
        self.y += (dy / distance) * self.speed
        return True

    def draw(self, screen: pygame.Surface, offset: tuple[float, float]) -> None:
        """Draw a dark arrow-like bolt."""
        draw_pos = (int(self.x - offset[0]), int(self.y - offset[1]))
        pygame.draw.circle(screen, (70, 70, 70), draw_pos, self.radius + 2)
        pygame.draw.circle(screen, BLACK, draw_pos, self.radius)


@dataclass(slots=True)
class ClickMarker:
    """Short-lived presentation marker for an issued world-space order."""

    x: float
    y: float
    color: tuple[int, int, int]
    created_at_ms: int
    duration_ms: int = 450

    def is_alive(self, now_ms: int) -> bool:
        """Return whether the marker is still inside its display lifetime."""
        return now_ms - self.created_at_ms < self.duration_ms

    def draw(self, screen: pygame.Surface, offset: tuple[float, float]) -> None:
        """Draw an expanding, fading confirmation ring."""
        elapsed = pygame.time.get_ticks() - self.created_at_ms
        progress = min(max(elapsed / self.duration_ms, 0.0), 1.0)
        alpha = int(220 * (1.0 - progress))
        radius = int(8 + progress * 22)
        draw_pos = (int(self.x - offset[0]), int(self.y - offset[1]))
        marker_surface = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
        center = marker_surface.get_width() // 2, marker_surface.get_height() // 2
        color = (*self.color, alpha)
        pygame.draw.circle(marker_surface, color, center, radius, width=3)
        pygame.draw.line(marker_surface, color, (center[0] - 6, center[1]), (center[0] + 6, center[1]), width=2)
        pygame.draw.line(marker_surface, color, (center[0], center[1] - 6), (center[0], center[1] + 6), width=2)
        screen.blit(marker_surface, marker_surface.get_rect(center=draw_pos))
