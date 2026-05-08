"""Terrain loading, collision semantics, and procedural rendering.

The terrain system is deliberately data-driven. JSON map files provide a
``Terrain`` object with dimensions, terrain regions, and decorative point
objects. Coordinates are always world coordinates, not screen coordinates.
Camera offsets are applied only when drawing.

Region payloads use the grouped rectangle format:

``"high_ground": [[[x, y, width, height], [x2, y2, width2, height2]]]``

Each outer list entry is one visual shape. A shape can contain one rectangle or
many touching/overlapping rectangles. Collision and height queries flatten those
groups into individual rectangles, while rendering preserves groups so joined
high ground or water draws as one continuous area.

Movement rules are intentionally simple:

* water and rocks block movement,
* high ground changes an entity's ``height_level``,
* height changes are allowed only when either endpoint is on a ramp.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


@dataclass(frozen=True)
class TerrainRegion:
    """One rectangular terrain area used for queries and rendering.

    Attributes:
        rect: World-space rectangle.
        level: Height level contributed by the region. High ground uses ``1``;
            ramps/water use ``0`` because they do not themselves create high
            ground.
        kind: Human-readable layer name used by drawing/debugging.
    """

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
    """Small circular visual object loaded from terrain settings.

    Rocks are also used as movement blockers, while grass is purely decorative.
    The shared shape keeps the JSON format compact: ``[x, y, radius]``.
    """

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
    """Store terrain features and answer terrain queries.

    Public attributes such as ``high_ground``, ``ramps``, and ``water`` are
    flattened lists kept for game logic and minimap drawing. The corresponding
    ``*_shapes`` attributes preserve grouped JSON shapes for the main renderer.
    Future code should use:

    * flattened lists for collision, pathfinding, and minimap rectangles,
    * grouped shapes for visual rendering of joined terrain.
    """

    def __init__(self, settings: Mapping[str, object] | None = None) -> None:
        """Initialize terrain from optional map settings.

        Missing or malformed terrain arrays are treated as empty. Width/height
        fall back to the original one-screen map size so older minimal maps keep
        loading.
        """
        settings = settings or {}
        self.width = self._load_dimension(settings.get("width"), default=1600)
        self.height = self._load_dimension(settings.get("height"), default=600)
        self.high_ground_shapes = self._load_region_groups(settings.get("high_ground"), level=1)
        self.ramp_shapes = self._load_region_groups(settings.get("ramps"), level=0, kind="ramp")
        self.water_shapes = self._load_region_groups(settings.get("water"), level=0, kind="water")
        self.high_ground: list[TerrainRegion] = self._flatten_region_groups(self.high_ground_shapes)
        self.ramps: list[TerrainRegion] = self._flatten_region_groups(self.ramp_shapes)
        self.water: list[TerrainRegion] = self._flatten_region_groups(self.water_shapes)
        self.grass: list[TerrainDecoration] = self._load_decorations(settings.get("grass"), kind="grass")
        self.rocks: list[TerrainDecoration] = self._load_decorations(settings.get("rocks"), kind="rocks")

    @staticmethod
    def _load_dimension(payload: object, *, default: int) -> int:
        """Read a positive map dimension from settings."""
        if isinstance(payload, (int, float)) and payload > 0:
            return int(payload)
        return default

    @staticmethod
    def _as_iterable(payload: object) -> Iterable[object]:
        """Normalize missing or malformed terrain lists."""
        if isinstance(payload, list):
            return payload
        return []

    def _load_regions(self, payload: object, *, level: int, kind: str = "high_ground") -> list[TerrainRegion]:
        """Load rectangular terrain regions."""
        return self._flatten_region_groups(self._load_region_groups(payload, level=level, kind=kind))

    def _load_region_groups(
        self,
        payload: object,
        *,
        level: int,
        kind: str = "high_ground",
    ) -> list[list[TerrainRegion]]:
        """Load terrain regions, preserving nested grouped shapes.

        The editor now saves ``high_ground`` and ``water`` exclusively as
        grouped shapes, but this loader is permissive and also accepts old flat
        ``[x, y, w, h]`` entries. That keeps archived maps and small hand-written
        test payloads usable.
        """
        regions: list[TerrainRegion] = []
        groups: list[list[TerrainRegion]] = []
        for item in self._as_iterable(payload):
            if self._is_region_payload(item):
                groups.append([TerrainRegion.from_payload(item, level=level, kind=kind)])
                continue
            regions = []
            for nested_item in self._as_iterable(item):
                if self._is_region_payload(nested_item):
                    regions.append(TerrainRegion.from_payload(nested_item, level=level, kind=kind))
            if regions:
                groups.append(regions)
        return groups

    @staticmethod
    def _flatten_region_groups(groups: list[list[TerrainRegion]]) -> list[TerrainRegion]:
        """Flatten grouped terrain regions for collision and height queries."""
        return [region for group in groups for region in group]

    @staticmethod
    def _is_region_payload(payload: object) -> bool:
        """Return whether a payload looks like [x, y, width, height]."""
        return (
            isinstance(payload, list)
            and len(payload) == 4
            and all(isinstance(value, (int, float)) for value in payload)
        )

    def _load_decorations(self, payload: object, *, kind: str) -> list[TerrainDecoration]:
        """Load visual map decorations."""
        return [TerrainDecoration.from_payload(item, kind=kind) for item in self._as_iterable(payload)]

    def height_at(self, point: tuple[float, float]) -> int:
        """Return the terrain height at a world position.

        High-ground rectangles are flattened for this query. If grouped shapes
        overlap, the first matching high-ground rectangle wins, but all current
        maps use a single high level so ordering does not matter.
        """
        for region in self.high_ground:
            if region.rect.collidepoint(point):
                return region.level
        return 0

    def allows_height_transition(self, current_point: tuple[float, float], next_point: tuple[float, float]) -> bool:
        """Return whether a movement step may cross between terrain levels.

        Units may freely move on the same height. Moving between low and high
        ground is allowed only when either the current or next point lies on a
        ramp. Pathfinding and per-frame movement both call this rule, so changing
        it affects strategic routes and local collision fallback.
        """
        current_height = self.height_at(current_point)
        next_height = self.height_at(next_point)
        if current_height == next_height:
            return True
        return self.is_on_ramp(current_point) or self.is_on_ramp(next_point)

    def is_on_ramp(self, point: tuple[float, float]) -> bool:
        """Return whether a point lies on a ramp connector."""
        return any(region.rect.collidepoint(point) for region in self.ramps)

    def blocks_movement(self, point: tuple[float, float], radius: float = 0) -> bool:
        """Return whether terrain blocks a unit centered at a world point.

        The optional ``radius`` inflates water rectangles and rock circles so
        unit centers cannot clip visually through blockers. Resource nodes are
        not terrain blockers; they are normal entities handled by collision and
        harvesting logic.
        """
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
        current_x, current_y = current_point
        next_x, next_y = next_point
        distance = math.hypot(next_x - current_x, next_y - current_y)
        step_size = 0.5
        steps = max(1, math.ceil(distance / step_size))

        previous_point = current_point
        for step in range(1, steps + 1):
            t = step / steps
            sample_point = (
                current_x + (next_x - current_x) * t,
                current_y + (next_y - current_y) * t,
            )
            if self.blocks_movement(sample_point, radius):
                return False
            if not self.allows_height_transition(previous_point, sample_point):
                return False
            previous_point = sample_point
        return True

    def draw(self, screen: pygame.Surface, offset: tuple[float, float] = (0, 0)) -> None:
        """Draw terrain under entities.

        Args:
            screen: Surface representing only the playable world area.
            offset: Camera ``(x, y)`` subtracted from every world coordinate.

        This method redraws procedural ground each frame. It does not clip or
        cull off-screen regions; maps are small enough that straightforward
        drawing is easier to reason about.
        """
        offset_x, offset_y = int(offset[0]), int(offset[1])
        self._draw_ground(screen)
        for shape in self.water_shapes:
            self._draw_water_shape(screen, [region.rect.move(-offset_x, -offset_y) for region in shape])
        for shape in self.high_ground_shapes:
            self._draw_high_ground_shape(screen, [region.rect.move(-offset_x, -offset_y) for region in shape])
        for shape in self.ramp_shapes:
            for region in shape:
                self._draw_ramp(screen, region.rect.move(-offset_x, -offset_y))
        for decoration in self.grass:
            self._draw_grass(screen, decoration, offset)
        for decoration in self.rocks:
            self._draw_rocks(screen, decoration, offset)

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
        self._draw_high_ground_shape(screen, [rect])

    def _draw_high_ground_shape(self, screen: pygame.Surface, rects: list[pygame.Rect]) -> None:
        """Draw one high-ground shape made from one or more rectangles."""
        if len(rects) == 1:
            self._draw_legacy_high_ground(screen, rects[0])
            return

        for rect in rects:
            shadow = rect.move(10, 10)
            pygame.draw.rect(screen, (55, 68, 51), shadow)
        for rect in rects:
            pygame.draw.rect(screen, (113, 132, 77), rect)
        self._draw_shape_outline(screen, rects, (64, 77, 57), width=4)
        self._draw_shape_outline(screen, [rect.inflate(-10, -10) for rect in rects], (154, 167, 103), width=3)

    def _draw_shape_outline(
        self,
        screen: pygame.Surface,
        rects: list[pygame.Rect],
        color: tuple[int, int, int],
        *,
        width: int,
    ) -> None:
        """Draw only the outside outline of a grouped rectangle shape.

        Grouped terrain is represented as multiple rectangles. Drawing a normal
        outline for each rectangle creates visible internal seams. This routine
        subtracts covered edge spans so only the exterior boundary remains.
        """
        for rect in rects:
            for start, end in self._visible_horizontal_segments(rect.left, rect.right, rect.top, -1, rects):
                pygame.draw.line(screen, color, (start, rect.top), (end, rect.top), width)
            for start, end in self._visible_horizontal_segments(rect.left, rect.right, rect.bottom, 1, rects):
                pygame.draw.line(screen, color, (start, rect.bottom), (end, rect.bottom), width)
            for start, end in self._visible_vertical_segments(rect.top, rect.bottom, rect.left, -1, rects):
                pygame.draw.line(screen, color, (rect.left, start), (rect.left, end), width)
            for start, end in self._visible_vertical_segments(rect.top, rect.bottom, rect.right, 1, rects):
                pygame.draw.line(screen, color, (rect.right, start), (rect.right, end), width)

    @staticmethod
    def _visible_horizontal_segments(
        left: int,
        right: int,
        y: int,
        outward_step: int,
        rects: list[pygame.Rect],
    ) -> list[tuple[int, int]]:
        """Return horizontal edge segments not covered by the grouped shape."""
        covered: list[tuple[int, int]] = []
        for other in rects:
            if other.collidepoint(max(other.left, min(left, other.right - 1)), y + outward_step):
                overlap_left = max(left, other.left)
                overlap_right = min(right, other.right)
                if overlap_left < overlap_right:
                    covered.append((overlap_left, overlap_right))
        return TerrainMap._subtract_segments((left, right), covered)

    @staticmethod
    def _visible_vertical_segments(
        top: int,
        bottom: int,
        x: int,
        outward_step: int,
        rects: list[pygame.Rect],
    ) -> list[tuple[int, int]]:
        """Return vertical edge segments not covered by the grouped shape."""
        covered: list[tuple[int, int]] = []
        for other in rects:
            if other.collidepoint(x + outward_step, max(other.top, min(top, other.bottom - 1))):
                overlap_top = max(top, other.top)
                overlap_bottom = min(bottom, other.bottom)
                if overlap_top < overlap_bottom:
                    covered.append((overlap_top, overlap_bottom))
        return TerrainMap._subtract_segments((top, bottom), covered)

    @staticmethod
    def _subtract_segments(base: tuple[int, int], covered: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Subtract covered intervals from one base interval."""
        visible = [base]
        for cover_start, cover_end in covered:
            next_visible: list[tuple[int, int]] = []
            for start, end in visible:
                if cover_end <= start or cover_start >= end:
                    next_visible.append((start, end))
                    continue
                if start < cover_start:
                    next_visible.append((start, cover_start))
                if cover_end < end:
                    next_visible.append((cover_end, end))
            visible = next_visible
        return [(start, end) for start, end in visible if start < end]

    def _draw_legacy_high_ground(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw a raised plateau using the pre-grouped renderer."""
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
        self._draw_water_shape(screen, [rect])

    def _draw_water_shape(self, screen: pygame.Surface, rects: list[pygame.Rect]) -> None:
        """Draw one water shape made from one or more rectangles."""
        if len(rects) == 1:
            self._draw_legacy_water(screen, rects[0])
            return

        for rect in rects:
            pygame.draw.rect(screen, (43, 92, 119), rect)
        for rect in rects:
            for y in range(rect.top + 12, rect.bottom, 22):
                pygame.draw.arc(screen, (78, 144, 162), (rect.left + 8, y, rect.width - 16, 18), 0.1, 3.0, 2)
        self._draw_shape_outline(screen, rects, (30, 70, 95), width=2)

    def _draw_legacy_water(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw a shallow decorative water patch using the pre-grouped renderer."""
        pygame.draw.rect(screen, (43, 92, 119), rect, border_radius=14)
        for y in range(rect.top + 12, rect.bottom, 22):
            pygame.draw.arc(screen, (78, 144, 162), (rect.left + 8, y, rect.width - 16, 18), 0.1, 3.0, 2)

    def _draw_grass(
        self,
        screen: pygame.Surface,
        decoration: TerrainDecoration,
        offset: tuple[float, float] = (0, 0),
    ) -> None:
        """Draw a small grass tuft."""
        offset_x, offset_y = offset
        draw_x = int(decoration.x - offset_x)
        draw_y = int(decoration.y - offset_y)
        color = (121, 150, 63)
        for blade_offset in (-6, 0, 6):
            pygame.draw.line(
                screen,
                color,
                (draw_x + blade_offset, draw_y + decoration.radius),
                (draw_x + blade_offset // 2, draw_y - decoration.radius),
                2,
            )

    def _draw_rocks(
        self,
        screen: pygame.Surface,
        decoration: TerrainDecoration,
        offset: tuple[float, float] = (0, 0),
    ) -> None:
        """Draw a small cluster of stones."""
        offset_x, offset_y = offset
        draw_x = int(decoration.x - offset_x)
        draw_y = int(decoration.y - offset_y)
        pygame.draw.circle(screen, (88, 91, 84), (draw_x, draw_y), decoration.radius)
        pygame.draw.circle(
            screen,
            (114, 117, 108),
            (draw_x - decoration.radius // 2, draw_y - decoration.radius // 3),
            max(2, decoration.radius // 2),
        )
