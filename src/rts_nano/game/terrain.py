"""Map terrain state and rendering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class TerrainRegion:
    """Rectangular terrain region loaded from map settings."""

    rect: pygame.Rect
    level: int
    kind: str

    @classmethod
    def from_payload(cls, payload: object, *, level: int, kind: str) -> TerrainRegion:
        """Build a terrain region from a JSON array: x, y, width, height."""
        match payload:
            case [int() | float() as x, int() | float() as y, int() | float() as width, int() | float() as height]:
                return cls(pygame.Rect(int(x), int(y), int(width), int(height)), level, kind)
        raise TypeError(f"Invalid terrain region: {payload!r}")


@dataclass(frozen=True)
class TerrainDecoration:
    """Small visual-only map object."""

    x: int
    y: int
    radius: int
    kind: str

    @classmethod
    def from_payload(cls, payload: object, *, kind: str) -> TerrainDecoration:
        """Build a decoration from a JSON array: x, y, radius."""
        match payload:
            case [int() | float() as x, int() | float() as y, int() | float() as radius]:
                return cls(int(x), int(y), int(radius), kind)
        raise TypeError(f"Invalid terrain decoration: {payload!r}")


class TerrainMap:
    """Store terrain features and expose height queries."""

    def __init__(self, settings: dict[str, object] | None = None) -> None:
        """Initialize terrain from optional map settings."""
        settings = settings or {}
        self.high_ground: list[TerrainRegion] = self._load_regions(settings.get("high_ground"), level=1)
        self.ramps: list[TerrainRegion] = self._load_regions(settings.get("ramps"), level=0, kind="ramp")
        self.water: list[TerrainRegion] = self._load_regions(settings.get("water"), level=0, kind="water")
        self.grass: list[TerrainDecoration] = self._load_decorations(settings.get("grass"), kind="grass")
        self.rocks: list[TerrainDecoration] = self._load_decorations(settings.get("rocks"), kind="rocks")

    @staticmethod
    def _as_iterable(payload: object) -> Iterable[object]:
        """Normalize missing or malformed terrain lists."""
        if isinstance(payload, list):
            return payload
        return []

    def _load_regions(self, payload: object, *, level: int, kind: str = "high_ground") -> list[TerrainRegion]:
        """Load rectangular terrain regions."""
        return [TerrainRegion.from_payload(item, level=level, kind=kind) for item in self._as_iterable(payload)]

    def _load_decorations(self, payload: object, *, kind: str) -> list[TerrainDecoration]:
        """Load visual map decorations."""
        return [TerrainDecoration.from_payload(item, kind=kind) for item in self._as_iterable(payload)]

    def height_at(self, point: tuple[float, float]) -> int:
        """Return the terrain height at a map position."""
        for region in self.high_ground:
            if region.rect.collidepoint(point):
                return region.level
        return 0

    def allows_height_transition(self, current_point: tuple[float, float], next_point: tuple[float, float]) -> bool:
        """Return whether a movement step may cross between terrain levels."""
        current_height = self.height_at(current_point)
        next_height = self.height_at(next_point)
        if current_height == next_height:
            return True
        return self.is_on_ramp(current_point) or self.is_on_ramp(next_point)

    def is_on_ramp(self, point: tuple[float, float]) -> bool:
        """Return whether a point lies on a ramp connector."""
        return any(region.rect.collidepoint(point) for region in self.ramps)

    def blocks_movement(self, point: tuple[float, float], radius: float = 0) -> bool:
        """Return whether terrain blocks a unit centered at point."""
        x, y = point
        for region in self.water:
            if region.rect.inflate(radius * 2, radius * 2).collidepoint(x, y):
                return True
        for rock in self.rocks:
            dx = x - rock.x
            dy = y - rock.y
            if (dx**2 + dy**2) ** 0.5 < radius + rock.radius:
                return True
        return False

    def can_move_between(
        self,
        current_point: tuple[float, float],
        next_point: tuple[float, float],
        *,
        radius: float,
    ) -> bool:
        """Return whether a unit may move from current point to next point."""
        if self.blocks_movement(next_point, radius):
            return False
        return self.allows_height_transition(current_point, next_point)

    def draw(self, screen: pygame.Surface) -> None:
        """Draw terrain under entities."""
        self._draw_ground(screen)
        for region in self.water:
            self._draw_water(screen, region.rect)
        for region in self.high_ground:
            self._draw_high_ground(screen, region.rect)
        for region in self.ramps:
            self._draw_ramp(screen, region.rect)
        for decoration in self.grass:
            self._draw_grass(screen, decoration)
        for decoration in self.rocks:
            self._draw_rocks(screen, decoration)

    def _draw_ground(self, screen: pygame.Surface) -> None:
        """Draw a simple procedural ground texture."""
        screen.fill((78, 104, 67))
        width, height = screen.get_size()
        for x in range(0, width, 80):
            pygame.draw.line(screen, (67, 91, 58), (x, 0), (x, height), 1)
        for y in range(0, height, 80):
            pygame.draw.line(screen, (89, 116, 74), (0, y), (width, y), 1)

    def _draw_high_ground(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw a raised plateau."""
        shadow = rect.move(10, 10)
        pygame.draw.rect(screen, (55, 68, 51), shadow, border_radius=10)
        pygame.draw.rect(screen, (113, 132, 77), rect, border_radius=10)
        pygame.draw.rect(screen, (154, 167, 103), rect.inflate(-10, -10), width=3, border_radius=8)
        pygame.draw.rect(screen, (64, 77, 57), rect, width=4, border_radius=10)

    def _draw_ramp(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw a slope that connects low and high terrain."""
        pygame.draw.rect(screen, (128, 113, 79), rect, border_radius=5)
        pygame.draw.rect(screen, (77, 72, 58), rect, width=2, border_radius=5)
        if rect.width >= rect.height:
            for x in range(rect.left + 8, rect.right, 14):
                pygame.draw.line(screen, (158, 142, 96), (x, rect.top + 4), (x - 10, rect.bottom - 4), 2)
        else:
            for y in range(rect.top + 8, rect.bottom, 14):
                pygame.draw.line(screen, (158, 142, 96), (rect.left + 4, y), (rect.right - 4, y - 10), 2)

    def _draw_water(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw a shallow decorative water patch."""
        pygame.draw.rect(screen, (43, 92, 119), rect, border_radius=14)
        for y in range(rect.top + 12, rect.bottom, 22):
            pygame.draw.arc(screen, (78, 144, 162), (rect.left + 8, y, rect.width - 16, 18), 0.1, 3.0, 2)

    def _draw_grass(self, screen: pygame.Surface, decoration: TerrainDecoration) -> None:
        """Draw a small grass tuft."""
        color = (121, 150, 63)
        for offset in (-6, 0, 6):
            pygame.draw.line(
                screen,
                color,
                (decoration.x + offset, decoration.y + decoration.radius),
                (decoration.x + offset // 2, decoration.y - decoration.radius),
                2,
            )

    def _draw_rocks(self, screen: pygame.Surface, decoration: TerrainDecoration) -> None:
        """Draw a small cluster of stones."""
        pygame.draw.circle(screen, (88, 91, 84), (decoration.x, decoration.y), decoration.radius)
        pygame.draw.circle(
            screen,
            (114, 117, 108),
            (decoration.x - decoration.radius // 2, decoration.y - decoration.radius // 3),
            max(2, decoration.radius // 2),
        )
