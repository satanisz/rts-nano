"""Pygame presentation adapter for pure terrain data."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from rts_nano.game.terrain import TerrainDecoration, TerrainMap, TerrainRegion
    from rts_nano.simulation.geometry import Rect


class TerrainRenderer:
    """Draw procedural terrain without adding presentation methods to terrain state."""

    def draw(self, screen: pygame.Surface, terrain: TerrainMap, offset: tuple[float, float]) -> None:
        """Draw terrain shapes and decorations relative to a camera offset."""
        self._draw_ground(screen)
        for shape in terrain.water_shapes:
            self._draw_water_shape(screen, shape, offset)
        for shape in terrain.high_ground_shapes:
            self._draw_high_ground_shape(screen, shape, offset)
        for shape in terrain.ramp_shapes:
            for region in shape:
                self._draw_ramp(screen, self._screen_rect(region.rect, offset))
        for decoration in terrain.grass:
            self._draw_grass(screen, decoration, offset)
        for decoration in terrain.rocks:
            self._draw_rocks(screen, decoration, offset)

    @staticmethod
    def _screen_rect(rect: Rect, offset: tuple[float, float]) -> pygame.Rect:
        return pygame.Rect(
            rect.x - int(offset[0]),
            rect.y - int(offset[1]),
            rect.width,
            rect.height,
        )

    @staticmethod
    def _draw_ground(screen: pygame.Surface) -> None:
        screen.fill((78, 104, 67))
        width, height = screen.get_size()
        for x in range(0, width, 80):
            pygame.draw.line(screen, (67, 91, 58), (x, 0), (x, height), 1)
        for y in range(0, height, 80):
            pygame.draw.line(screen, (89, 116, 74), (0, y), (width, y), 1)

    def _draw_high_ground_shape(
        self,
        screen: pygame.Surface,
        shape: list[TerrainRegion],
        offset: tuple[float, float],
    ) -> None:
        rects = [self._screen_rect(region.rect, offset) for region in shape]
        for rect in rects:
            pygame.draw.rect(screen, (55, 68, 51), rect.move(10, 10), border_radius=10)
        for rect in rects:
            pygame.draw.rect(screen, (113, 132, 77), rect, border_radius=10)
            pygame.draw.rect(screen, (154, 167, 103), rect.inflate(-10, -10), width=3, border_radius=8)
            pygame.draw.rect(screen, (64, 77, 57), rect, width=4, border_radius=10)

    def _draw_water_shape(
        self,
        screen: pygame.Surface,
        shape: list[TerrainRegion],
        offset: tuple[float, float],
    ) -> None:
        for region in shape:
            rect = self._screen_rect(region.rect, offset)
            pygame.draw.rect(screen, (43, 92, 119), rect, border_radius=14)
            for y in range(rect.top + 12, rect.bottom, 22):
                pygame.draw.arc(screen, (78, 144, 162), (rect.left + 8, y, rect.width - 16, 18), 0.1, 3.0, 2)

    @staticmethod
    def _draw_ramp(screen: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(screen, (128, 113, 79), rect, border_radius=5)
        pygame.draw.rect(screen, (77, 72, 58), rect, width=2, border_radius=5)
        if rect.width >= rect.height:
            for x in range(rect.left + 8, rect.right, 14):
                pygame.draw.line(screen, (158, 142, 96), (x, rect.top + 4), (x - 10, rect.bottom - 4), 2)
        else:
            for y in range(rect.top + 8, rect.bottom, 14):
                pygame.draw.line(screen, (158, 142, 96), (rect.left + 4, y), (rect.right - 4, y - 10), 2)

    @staticmethod
    def _draw_grass(
        screen: pygame.Surface,
        decoration: TerrainDecoration,
        offset: tuple[float, float],
    ) -> None:
        draw_x = int(decoration.x - offset[0])
        draw_y = int(decoration.y - offset[1])
        for blade_offset in (-6, 0, 6):
            pygame.draw.line(
                screen,
                (121, 150, 63),
                (draw_x + blade_offset, draw_y + decoration.radius),
                (draw_x + blade_offset // 2, draw_y - decoration.radius),
                2,
            )

    @staticmethod
    def _draw_rocks(
        screen: pygame.Surface,
        decoration: TerrainDecoration,
        offset: tuple[float, float],
    ) -> None:
        draw_x = int(decoration.x - offset[0])
        draw_y = int(decoration.y - offset[1])
        pygame.draw.circle(screen, (88, 91, 84), (draw_x, draw_y), decoration.radius)
        pygame.draw.circle(
            screen,
            (114, 117, 108),
            (draw_x - decoration.radius // 2, draw_y - decoration.radius // 3),
            max(2, decoration.radius // 2),
        )
