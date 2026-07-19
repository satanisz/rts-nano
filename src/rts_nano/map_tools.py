"""Text inspection and dependency-free SVG previews for compiled maps."""

from __future__ import annotations

import json
import math
from html import escape
from typing import TYPE_CHECKING, cast

from rts_nano.content import CONTENT
from rts_nano.game.pathfinding import find_path
from rts_nano.game.terrain import TerrainMap
from rts_nano.map_schema import load_map_settings

if TYPE_CHECKING:
    from pathlib import Path

    from rts_nano.map_schema import MapSettings


def inspect_map_file(path: Path) -> str:
    """Return an LLM-readable strategic summary and coarse spatial grid."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    settings = load_map_settings(path)
    metadata = raw if isinstance(raw, dict) else {}
    return inspect_map(settings, metadata=cast("dict[str, object]", metadata), source=path)


def inspect_map(
    settings: MapSettings,
    *,
    metadata: dict[str, object] | None = None,
    source: Path | None = None,
) -> str:
    """Summarize dimensions, economy, reachability, terrain, and layout."""
    terrain_payload = settings["Terrain"]
    terrain = TerrainMap(terrain_payload)
    width = terrain.width
    height = terrain.height
    lines = [f"Map: {_map_name(metadata, source)}", f"World: {width} x {height}"]
    if metadata and metadata.get("schema_version") == 3:
        symmetry = metadata.get("symmetry", {})
        if isinstance(symmetry, dict):
            symmetry_payload = cast("dict[str, object]", symmetry)
            lines.append(f"Symmetry: {symmetry_payload.get('type', 'none')}")

    resources = settings["Resources"]
    wood = resources.get("wood", [])
    gold = resources.get("gold", [])
    lines.append(f"Resources: wood={len(wood)}, gold={len(gold)}")
    lines.append(
        "Terrain: "
        f"high_ground={len(terrain.high_ground_shapes)}, ramps={len(terrain.ramps)}, "
        f"water={len(terrain.water_shapes)}, rocks={len(terrain.rocks)}, grass={len(terrain.grass)}"
    )
    lines.append(f"Approximate blocking coverage: {_blocking_coverage(terrain):.1f}%")

    center = (width / 2, height / 2)
    for team_id in ("Blue", "Red"):
        team = settings[team_id]
        bases = team.get("base", [])
        unit_count = sum(len(team.get(content_id, [])) for content_id in CONTENT.units)
        building_count = sum(len(team.get(content_id, [])) for content_id in CONTENT.buildings)
        lines.extend(["", f"{team_id} ({team['faction_id']}):", f"  Units: {unit_count}; buildings: {building_count}"])
        if not bases:
            lines.append("  Base: missing")
            continue
        base = bases[0]
        lines.append(f"  Base: ({base[0]}, {base[1]})")
        lines.append(f"  Nearest wood: {_nearest_distance(base, wood)}")
        lines.append(f"  Nearest gold: {_nearest_distance(base, gold)}")
        lines.append(f"  Route to center: {'reachable' if _reachable(terrain, base, center) else 'blocked'}")

    lines.extend(["", "ASCII overview:", _ascii_overview(settings)])
    return "\n".join(lines)


def render_map_svg(settings: MapSettings, *, title: str = "RTS Nano map") -> str:
    """Render a scalable map preview without importing Pygame."""
    terrain = settings["Terrain"]
    width = terrain["width"]
    height = terrain["height"]
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">',
        f"<title>{escape(title)}</title>",
        f'<rect width="{width}" height="{height}" fill="#486b3c"/>',
    ]
    for group in terrain.get("high_ground", []):
        for x, y, rect_width, rect_height in group:
            parts.append(_svg_rect(x, y, rect_width, rect_height, "#8f8159", opacity=0.9))
    for group in terrain.get("water", []):
        for x, y, rect_width, rect_height in group:
            parts.append(_svg_rect(x, y, rect_width, rect_height, "#3977a8", opacity=0.95))
    for x, y, rect_width, rect_height in terrain.get("ramps", []):
        parts.append(_svg_rect(x, y, rect_width, rect_height, "#b69b68", opacity=0.95))
    for x, y, radius in terrain.get("rocks", []):
        parts.append(_svg_circle(x, y, radius, "#555b60"))
    for x, y, radius in terrain.get("grass", []):
        parts.append(_svg_circle(x, y, radius, "#75a94f", opacity=0.65))

    for x, y in settings["Resources"].get("wood", []):
        parts.append(_svg_circle(x, y, CONTENT.get_resource("wood").radius, "#245c2c"))
    for x, y in settings["Resources"].get("gold", []):
        parts.append(_svg_circle(x, y, CONTENT.get_resource("gold").radius, "#e3bd2d"))

    for team_id, color in (("Blue", "#3c74db"), ("Red", "#c74646")):
        team = settings[team_id]
        for content_id in (*CONTENT.buildings, *CONTENT.units):
            definition = CONTENT.buildings.get(content_id) or CONTENT.units.get(content_id)
            if definition is None:
                continue
            for x, y in team.get(content_id, []):
                parts.append(_svg_circle(x, y, definition.radius, color, stroke="#ffffff"))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _map_name(metadata: dict[str, object] | None, source: Path | None) -> str:
    if metadata:
        name = metadata.get("name") or metadata.get("id")
        if isinstance(name, str):
            return name
    return source.stem if source is not None else "unnamed"


def _nearest_distance(origin: list[int], targets: list[list[int]]) -> str:
    if not targets:
        return "missing"
    distance = min(math.hypot(origin[0] - target[0], origin[1] - target[1]) for target in targets)
    return str(round(distance))


def _reachable(terrain: TerrainMap, start: list[int], goal: tuple[float, float]) -> bool:
    start_point = (float(start[0]), float(start[1]))
    if terrain.can_move_between(start_point, goal, radius=8):
        return True
    return bool(
        find_path(
            start_point,
            goal,
            width=terrain.width,
            height=terrain.height,
            can_move_between=lambda current, next_point: terrain.can_move_between(current, next_point, radius=8),
        )
    )


def _blocking_coverage(terrain: TerrainMap) -> float:
    blocked_area = sum(region.rect.width * region.rect.height for region in terrain.water)
    blocked_area += sum(math.pi * rock.radius**2 for rock in terrain.rocks)
    world_area = terrain.width * terrain.height
    return min(100.0, blocked_area / world_area * 100) if world_area else 0.0


def _ascii_overview(settings: MapSettings, columns: int = 48) -> str:
    terrain = TerrainMap(settings["Terrain"])
    rows = max(8, round(columns * terrain.height / terrain.width / 2))
    grid = [["." for _ in range(columns)] for _ in range(rows)]

    def cell(point: tuple[float, float]) -> tuple[int, int]:
        column = min(columns - 1, max(0, int(point[0] / max(1, terrain.width) * columns)))
        row = min(rows - 1, max(0, int(point[1] / max(1, terrain.height) * rows)))
        return column, row

    for row in range(rows):
        for column in range(columns):
            point = ((column + 0.5) / columns * terrain.width, (row + 0.5) / rows * terrain.height)
            if terrain.blocks_movement(point):
                grid[row][column] = "~"
            elif terrain.height_at(point) > 0:
                grid[row][column] = "^"
    for resource_id, marker in (("wood", "W"), ("gold", "G")):
        for x, y in settings["Resources"].get(resource_id, []):
            column, row = cell((x, y))
            grid[row][column] = marker
    for team_id, marker in (("Blue", "B"), ("Red", "R")):
        for x, y in settings[team_id].get("base", []):
            column, row = cell((x, y))
            grid[row][column] = marker
    return "\n".join("".join(row) for row in grid) + "\nLegend: B/R bases, W wood, G gold, ~=blocking, ^=high ground"


def _svg_rect(x: int, y: int, width: int, height: int, fill: str, *, opacity: float) -> str:
    return f'<rect x="{x}" y="{y}" width="{width}" height="{height}" fill="{fill}" opacity="{opacity}"/>'


def _svg_circle(
    x: int | float,
    y: int | float,
    radius: int | float,
    fill: str,
    *,
    opacity: float = 1.0,
    stroke: str = "none",
) -> str:
    return (
        f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" opacity="{opacity}" stroke="{stroke}" stroke-width="2"/>'
    )
