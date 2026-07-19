"""Pure terrain loading, geometry, and collision semantics.

The terrain system is deliberately data-driven. JSON map files provide a
``Terrain`` object with dimensions, terrain regions, and decorative point
objects. Coordinates are always world coordinates, not screen coordinates.
Presentation adapters consume these world-space structures without mutating them.

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

from rts_nano.simulation.geometry import Rect

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

    rect: Rect
    level: int
    kind: str

    @classmethod
    def from_payload(cls, payload: object, *, level: int, kind: str) -> TerrainRegion:
        """Build a terrain region from a JSON array: x, y, width, height."""
        match payload:
            case [int() | float() as x, int() | float() as y, int() | float() as width, int() | float() as height]:
                return cls(Rect(int(x), int(y), int(width), int(height)), level, kind)
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

    def _segment_blocks_movement(
        self,
        current_point: tuple[float, float],
        next_point: tuple[float, float],
        radius: float,
    ) -> bool:
        """Return whether a movement segment intersects water or rocks."""
        if self.blocks_movement(next_point, radius):
            return True

        for region in self.water:
            if region.rect.inflate(radius * 2, radius * 2).clipline(current_point, next_point):
                return True
        for rock in self.rocks:
            if self._distance_point_to_segment((rock.x, rock.y), current_point, next_point) < radius + rock.radius:
                return True
        return False

    def _segment_allows_height_transition(
        self,
        current_point: tuple[float, float],
        next_point: tuple[float, float],
    ) -> bool:
        """Return whether segment high-ground crossings happen on ramps."""
        if self.height_at(current_point) == self.height_at(next_point):
            return True

        for region in self.high_ground:
            current_inside = region.rect.collidepoint(current_point)
            next_inside = region.rect.collidepoint(next_point)
            clipped_line = region.rect.clipline(current_point, next_point)
            if not clipped_line:
                continue

            if current_inside != next_inside:
                transition_point = clipped_line[1] if current_inside else clipped_line[0]
                if not self.is_on_ramp(transition_point):
                    return False
            elif not current_inside and not next_inside:
                entry_point, exit_point = clipped_line
                if not self.is_on_ramp(entry_point) or not self.is_on_ramp(exit_point):
                    return False
        return True

    @staticmethod
    def _distance_point_to_segment(
        point: tuple[float, float],
        segment_start: tuple[float, float],
        segment_end: tuple[float, float],
    ) -> float:
        """Return the shortest distance from a point to a line segment."""
        point_x, point_y = point
        start_x, start_y = segment_start
        end_x, end_y = segment_end
        dx = end_x - start_x
        dy = end_y - start_y
        length_squared = dx * dx + dy * dy
        if length_squared == 0:
            return math.hypot(point_x - start_x, point_y - start_y)

        t = ((point_x - start_x) * dx + (point_y - start_y) * dy) / length_squared
        t = min(max(t, 0), 1)
        closest_x = start_x + t * dx
        closest_y = start_y + t * dy
        return math.hypot(point_x - closest_x, point_y - closest_y)

    def can_move_between(
        self,
        current_point: tuple[float, float],
        next_point: tuple[float, float],
        *,
        radius: float,
    ) -> bool:
        """Return whether a unit may move from current point to next point."""
        if self._segment_blocks_movement(current_point, next_point, radius):
            return False
        return self._segment_allows_height_transition(current_point, next_point)
