"""Standalone pygame map editor for RTS Nano JSON maps.

The editor writes the same JSON schema consumed by the game. It is intentionally
separate from ``main.py`` so editor shortcuts, destructive operations, and map
creation do not complicate the playable game loop.

Coordinate model:

* mouse and camera positions are world coordinates plus screen offsets,
* the HUD occupies the bottom ``HUD_HEIGHT`` pixels,
* arrows and edge scrolling move the camera over maps larger than the window,
* optional grid snapping affects placement coordinates only.

Terrain model:

* ``high_ground`` and ``water`` are saved as grouped rectangle shapes,
  e.g. ``[[[x, y, w, h], [x2, y2, w2, h2]]]``.
* Adding high ground or water merges touching/overlapping groups so the game
  can render them as one continuous shape.
* ``ramps`` remain independent rectangles because they are connectors rather
  than filled terrain masses.

Destructive tools:

* right click removes from the currently selected layer,
* ``0 Erase`` removes any asset or terrain group at a point/area,
* ``X Flatten`` removes only terrain regions and leaves units/resources alone.
"""

from __future__ import annotations

import json
import sys
from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, cast

import pygame

from rts_nano.game.constants import BLACK, BLUE, FPS, RED, SCREEN_HEIGHT, SCREEN_WIDTH, WHITE, YELLOW
from rts_nano.game.terrain import TerrainMap

if TYPE_CHECKING:
    from collections.abc import Sequence

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MAP_PATH = BASE_DIR / "maps" / "map_settings_01.json"
MAPS_DIR = BASE_DIR / "maps"

CAMERA_SPEED = 18
EDGE_SCROLL_MARGIN = 24
GRID_SIZE = 32
HUD_HEIGHT = 92
DELETE_DISTANCE = 36

RESOURCE_TOOLS = {"wood", "gold"}
POINT_TERRAIN_TOOLS = {"rocks", "grass"}
RECT_TERRAIN_TOOLS = {"high_ground", "ramps", "water"}
MERGED_RECT_TOOLS = {"high_ground", "water"}
SPECIAL_TOOLS = {"erase", "flatten"}
ENTITY_TOOLS = {
    # Shared
    "blue_base",
    "blue_house",
    "blue_peasant",
    "red_base",
    "red_house",
    "red_peasant",
    # AEGIS (Blue)
    "blue_arsenal",
    "blue_spire",
    "blue_bastion",
    "blue_guardian",
    "blue_marksman",
    "blue_arclight",
    # RUST (Red)
    "red_pit",
    "red_chem_vat",
    "red_spiker",
    "red_ripper",
    "red_spitter",
    "red_brute",
}

TOOL_KEYS = {
    pygame.K_1: "wood",
    pygame.K_2: "gold",
    pygame.K_3: "rocks",
    pygame.K_4: "grass",
    pygame.K_5: "high_ground",
    pygame.K_6: "ramps",
    pygame.K_7: "water",
    pygame.K_8: "blue_base",
    pygame.K_9: "red_base",
    pygame.K_0: "erase",
    pygame.K_t: "blue_arsenal",
    pygame.K_g: "red_pit",
    pygame.K_y: "blue_house",
    pygame.K_h: "red_house",
    pygame.K_z: "blue_spire",
    pygame.K_c: "red_chem_vat",
    pygame.K_v: "blue_bastion",
    pygame.K_b: "red_spiker",
    pygame.K_q: "blue_peasant",
    pygame.K_w: "blue_guardian",
    pygame.K_e: "blue_marksman",
    pygame.K_r: "blue_arclight",
    pygame.K_a: "red_peasant",
    pygame.K_s: "red_ripper",
    pygame.K_d: "red_spitter",
    pygame.K_f: "red_brute",
    pygame.K_x: "flatten",
}

TOOL_LABELS = {
    "wood": "1 Wood",
    "gold": "2 Gold",
    "rocks": "3 Rocks",
    "grass": "4 Grass",
    "high_ground": "5 High ground",
    "ramps": "6 Ramp",
    "water": "7 Water",
    "blue_base": "8 Blue base",
    "red_base": "9 Red base",
    "erase": "0 Erase",
    "blue_arsenal": "T Blue arsenal",
    "red_pit": "G Red pit",
    "blue_house": "Y Blue house",
    "red_house": "H Red house",
    "blue_spire": "Z Blue spire",
    "red_chem_vat": "C Red chem vat",
    "blue_bastion": "V Blue bastion",
    "red_spiker": "B Red spiker",
    "blue_peasant": "Q Blue peasant",
    "blue_guardian": "W Blue guardian",
    "blue_marksman": "E Blue marksman",
    "blue_arclight": "R Blue arclight",
    "red_peasant": "A Red peasant",
    "red_ripper": "S Red ripper",
    "red_spitter": "D Red spitter",
    "red_brute": "F Red brute",
    "flatten": "X Flatten",
}


@dataclass
class MapEditor:
    """Interactive editor state for one map file.

    The object owns the mutable JSON payload, camera, current tool, drag state,
    and transient status text. It does not own the pygame process; ``main`` owns
    window creation and forwards events here.

    The editor mutates ``settings`` in memory and writes only on ``save`` or
    when creating a new map. Loading a map normalizes ``high_ground`` and
    ``water`` into grouped-shape format immediately, so simply opening and
    saving an older flat map upgrades those fields.
    """

    map_path: Path

    def __post_init__(self) -> None:
        """Load map data and initialize editing state."""
        self.settings = self._load_settings(self.map_path)
        self.camera_x = 0
        self.camera_y = 0
        self.tool = "wood"
        self.snap_to_grid = False
        self.show_grid = True
        self.drag_start: tuple[int, int] | None = None
        self.drag_current: tuple[int, int] | None = None
        self.status = f"Loaded {self.map_path.name}"
        self._normalize_grouped_terrain_payloads()

    @property
    def terrain_settings(self) -> dict[str, object]:
        """Return the mutable terrain settings block."""
        terrain = self.settings.setdefault("Terrain", {})
        if not isinstance(terrain, dict):
            raise TypeError("Terrain settings must be a JSON object.")
        return cast("dict[str, object]", terrain)

    @property
    def map_width(self) -> int:
        """Return map width from settings."""
        width = self.terrain_settings.get("width", SCREEN_WIDTH)
        return int(width) if isinstance(width, (int, float, str)) else SCREEN_WIDTH

    @property
    def map_height(self) -> int:
        """Return map height from settings."""
        height = self.terrain_settings.get("height", SCREEN_HEIGHT - HUD_HEIGHT)
        return int(height) if isinstance(height, (int, float, str)) else SCREEN_HEIGHT - HUD_HEIGHT

    @staticmethod
    def blank_settings(width: int = 3200, height: int = 2200) -> dict[str, object]:
        """Return a new empty map payload using the current canonical schema.

        The team dictionaries include all known entity keys so users can place
        units in any order without the editor having to infer missing sections.
        Terrain groups start empty but already use the grouped schema for
        ``high_ground`` and ``water``.
        """
        return {
            "Blue": {
                "peasant": [],
                "base": [],
                "house": [],
                "arsenal": [],
                "spire": [],
                "bastion": [],
                "guardian": [],
                "marksman": [],
                "arclight": [],
            },
            "Red": {
                "peasant": [],
                "base": [],
                "house": [],
                "pit": [],
                "chem_vat": [],
                "spiker": [],
                "ripper": [],
                "spitter": [],
                "brute": [],
            },
            "Resources": {"wood": [], "gold": []},
            "Terrain": {
                "width": width,
                "height": height,
                "high_ground": [],
                "ramps": [],
                "water": [],
                "rocks": [],
                "grass": [],
            },
        }

    @staticmethod
    def _load_settings(path: Path) -> dict[str, object]:
        """Read the map JSON file."""
        with path.open(encoding="utf-8") as map_file:
            settings = json.load(map_file)
        if not isinstance(settings, dict):
            raise TypeError("Map settings must be a JSON object.")
        return settings

    def load_map(self, map_path: Path) -> None:
        """Load another map file into the editor and reset transient state.

        The camera returns to the top-left corner and any active rectangle drag
        is canceled. This avoids accidentally finishing a drag on a different
        map after ``Ctrl+O``.
        """
        self.map_path = map_path
        self.settings = self._load_settings(map_path)
        self._normalize_grouped_terrain_payloads()
        self.camera_x = 0
        self.camera_y = 0
        self.drag_start = None
        self.drag_current = None
        self.status = f"Loaded {map_path.name}"

    def create_new_map(self, map_path: Path, *, width: int = 3200, height: int = 2200) -> None:
        """Create, save, and switch to a new blank map file."""
        map_path.parent.mkdir(parents=True, exist_ok=True)
        self.map_path = map_path
        self.settings = self.blank_settings(width=width, height=height)
        self._normalize_grouped_terrain_payloads()
        self.camera_x = 0
        self.camera_y = 0
        self.drag_start = None
        self.drag_current = None
        self.save()
        self.status = f"Created {map_path.name}"

    def save(self) -> None:
        """Write current map settings back to disk."""
        self._normalize_grouped_terrain_payloads()
        with self.map_path.open("w", encoding="utf-8") as map_file:
            json.dump(self.settings, map_file, indent=4)
            map_file.write("\n")
        self.status = f"Saved {self.map_path.name}"

    def _normalize_grouped_terrain_payloads(self) -> None:
        """Store high-ground and water as lists of rectangle groups.

        This is the editor's schema migration point. It accepts old flat
        rectangles and existing nested groups, then rewrites each shape as an
        outer list entry containing one or more ``[x, y, width, height]``
        rectangles. The game loader is permissive, but the editor always writes
        the new canonical format.
        """
        for key in MERGED_RECT_TOOLS:
            normalized_groups = []
            for payload in self._terrain_list(key):
                rects = self._payload_rects(payload)
                if rects:
                    normalized_groups.append([[rect.x, rect.y, rect.width, rect.height] for rect in rects])
            self.terrain_settings[key] = normalized_groups

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Process one pygame event and return whether editing should continue.

        Mouse-down starts placement or deletion. Mouse-up finalizes rectangle
        tools. Mouse-motion only matters during drags because ordinary hover
        information is derived directly from ``pygame.mouse.get_pos`` at draw
        time.
        """
        if event.type == pygame.QUIT:
            return False

        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_up(event)
        elif event.type == pygame.MOUSEMOTION and self.drag_start:
            self.drag_current = self._screen_to_world(event.pos)

        return True

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        """Handle editor keyboard shortcuts.

        ``Ctrl`` shortcuts are checked before tool keys, so ``Ctrl+S`` saves
        instead of selecting the red-ripper tool bound to ``S``.
        """
        if event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
            self.save()
        elif event.key == pygame.K_o and event.mod & pygame.KMOD_CTRL:
            self.load_next_map()
        elif event.key == pygame.K_n and event.mod & pygame.KMOD_CTRL:
            self.create_new_map(self._next_new_map_path(), width=self.map_width, height=self.map_height)
        elif event.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif event.key in TOOL_KEYS:
            self.tool = TOOL_KEYS[event.key]
            self.status = f"Tool: {self.tool}"
        elif event.key == pygame.K_g:
            self.show_grid = not self.show_grid
        elif event.key == pygame.K_TAB:
            self.snap_to_grid = not self.snap_to_grid
            self.status = f"Snap: {'ON' if self.snap_to_grid else 'OFF'}"

    def load_next_map(self) -> None:
        """Cycle through JSON maps in the maps directory."""
        map_paths = sorted(MAPS_DIR.glob("*.json"))
        if not map_paths:
            self.status = "No maps found"
            return
        try:
            current_index = map_paths.index(self.map_path)
        except ValueError:
            current_index = -1
        self.load_map(map_paths[(current_index + 1) % len(map_paths)])

    @staticmethod
    def _next_new_map_path() -> Path:
        """Return a non-existing map path for a new map."""
        index = 1
        while True:
            path = MAPS_DIR / f"map_settings_new_{index:02}.json"
            if not path.exists():
                return path
            index += 1

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        """Handle mouse press for placement, deletion, or rectangle start.

        Left click places point-like tools immediately. Rectangle and special
        tools start a drag so the release event can decide whether this was a
        point operation or an area operation. Right click always deletes from
        the currently selected layer.
        """
        if event.pos[1] >= SCREEN_HEIGHT - HUD_HEIGHT:
            return

        world_pos = self._screen_to_world(event.pos)
        if event.button == 1:
            if self.tool in RECT_TERRAIN_TOOLS or self.tool in SPECIAL_TOOLS:
                self.drag_start = world_pos
                self.drag_current = world_pos
            else:
                self._add_point_item(world_pos)
        elif event.button == 3:
            self._remove_nearest_item(world_pos)

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        """Finish rectangle placement."""
        if event.button != 1 or self.drag_start is None:
            return
        rect = self._normalized_rect(self.drag_start, self._screen_to_world(event.pos))
        if self.tool in RECT_TERRAIN_TOOLS and rect.width >= 8 and rect.height >= 8:
            self._add_rect_item(self.tool, rect)
        elif self.tool == "erase":
            self._erase_area_or_point(rect, self.drag_start)
        elif self.tool == "flatten":
            self._flatten_area_or_point(rect, self.drag_start)
        self.drag_start = None
        self.drag_current = None

    def update(self) -> None:
        """Move the editor camera."""
        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        if keys[pygame.K_LEFT]:
            dx -= CAMERA_SPEED
        if keys[pygame.K_RIGHT]:
            dx += CAMERA_SPEED
        if keys[pygame.K_UP]:
            dy -= CAMERA_SPEED
        if keys[pygame.K_DOWN]:
            dy += CAMERA_SPEED

        mouse_x, mouse_y = pygame.mouse.get_pos()
        if 0 <= mouse_y < SCREEN_HEIGHT - HUD_HEIGHT:
            if mouse_x <= EDGE_SCROLL_MARGIN:
                dx -= CAMERA_SPEED
            elif mouse_x >= SCREEN_WIDTH - EDGE_SCROLL_MARGIN:
                dx += CAMERA_SPEED
            if mouse_y <= EDGE_SCROLL_MARGIN:
                dy -= CAMERA_SPEED
            elif mouse_y >= SCREEN_HEIGHT - HUD_HEIGHT - EDGE_SCROLL_MARGIN:
                dy += CAMERA_SPEED

        self.camera_x = min(max(self.camera_x + dx, 0), max(0, self.map_width - SCREEN_WIDTH))
        self.camera_y = min(max(self.camera_y + dy, 0), max(0, self.map_height - (SCREEN_HEIGHT - HUD_HEIGHT)))

    def draw(self, screen: pygame.Surface) -> None:
        """Render the edited map, overlays, and controls."""
        play_area = screen.subsurface(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT - HUD_HEIGHT))
        TerrainMap(self.terrain_settings).draw(play_area, (self.camera_x, self.camera_y))
        if self.show_grid:
            self._draw_grid(play_area)
        self._draw_resources(play_area)
        self._draw_entities(play_area)
        self._draw_pending_rect(play_area)
        self._draw_hud(screen)

    def _screen_to_world(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Convert screen coordinates to map coordinates."""
        world_x = int(pos[0] + self.camera_x)
        world_y = int(pos[1] + self.camera_y)
        if self.snap_to_grid:
            world_x = round(world_x / GRID_SIZE) * GRID_SIZE
            world_y = round(world_y / GRID_SIZE) * GRID_SIZE
        return min(max(world_x, 0), self.map_width), min(max(world_y, 0), self.map_height)

    def _world_to_screen(self, pos: Sequence[int]) -> tuple[int, int]:
        """Convert map coordinates to screen coordinates."""
        return int(pos[0] - self.camera_x), int(pos[1] - self.camera_y)

    def _terrain_list(self, key: str) -> list[list[int]]:
        """Return a mutable terrain list, creating it if needed."""
        terrain_list = self.terrain_settings.setdefault(key, [])
        if not isinstance(terrain_list, list):
            raise TypeError(f"Terrain field {key!r} must be a list.")
        return cast("list[list[int]]", terrain_list)

    def _resource_list(self, key: str) -> list[list[int]]:
        """Return a mutable resource list, creating it if needed."""
        resources = self.settings.setdefault("Resources", {})
        if not isinstance(resources, dict):
            raise TypeError("Resources settings must be a JSON object.")
        resources_payload = cast("dict[str, object]", resources)
        resource_list = resources_payload.setdefault(key, [])
        if not isinstance(resource_list, list):
            raise TypeError(f"Resource field {key!r} must be a list.")
        return cast("list[list[int]]", resource_list)

    def _team_entity_list(self, tool: str) -> list[list[int]]:
        """Return a mutable team entity list for an entity tool."""
        team_name, entity_name = tool.split("_", maxsplit=1)
        team_key = team_name.title()
        team_settings = self.settings.setdefault(team_key, {})
        if not isinstance(team_settings, dict):
            raise TypeError(f"{team_key} settings must be a JSON object.")
        team_payload = cast("dict[str, object]", team_settings)
        entity_list = team_payload.setdefault(entity_name, [])
        if not isinstance(entity_list, list):
            raise TypeError(f"{team_key}.{entity_name} must be a list.")
        return cast("list[list[int]]", entity_list)

    def _add_point_item(self, world_pos: tuple[int, int]) -> None:
        """Place a resource, decoration, or entity."""
        if self.tool in RESOURCE_TOOLS:
            self._resource_list(self.tool).append([world_pos[0], world_pos[1]])
        elif self.tool == "rocks":
            self._terrain_list("rocks").append([world_pos[0], world_pos[1], 14])
        elif self.tool == "grass":
            self._terrain_list("grass").append([world_pos[0], world_pos[1], 8])
        elif self.tool in ENTITY_TOOLS:
            self._team_entity_list(self.tool).append([world_pos[0], world_pos[1]])
        self.status = f"Added {self.tool} at {world_pos[0]},{world_pos[1]}"

    def _add_rect_item(self, tool: str, rect: pygame.Rect) -> None:
        """Add a terrain rectangle, merging compatible terrain layers.

        ``high_ground`` and ``water`` are masses, so touching/overlapping
        rectangles join the same grouped shape. ``ramps`` stay flat because each
        ramp rectangle is a semantic connector used by movement rules.
        """
        if tool in MERGED_RECT_TOOLS:
            merged_rect, merged_count = self._merge_rect_payload(self._terrain_list(tool), rect)
            self.status = (
                f"Merged {tool}: {merged_rect.x},{merged_rect.y},{merged_rect.width},{merged_rect.height} "
                f"({merged_count} joined)"
            )
            return

        self._terrain_list(tool).append([rect.x, rect.y, rect.width, rect.height])
        self.status = f"Added {tool}: {rect.x},{rect.y},{rect.width},{rect.height}"

    def _merge_rect_payload(self, rect_payloads: list[list[int]], rect: pygame.Rect) -> tuple[pygame.Rect, int]:
        """Merge an added rectangle into a grouped multi-rectangle shape.

        The function removes every touching/overlapping group, appends all of
        their rectangles to a new group, and returns the group's bounding box for
        status text only. The bounding box is not saved as terrain; saving the
        exact rectangles avoids turning L-shaped terrain into a filled box.
        """
        grouped_payloads = [[rect.x, rect.y, rect.width, rect.height]]
        merged_count = 0
        bounds = rect.copy()
        changed = True
        while changed:
            changed = False
            for index in range(len(rect_payloads) - 1, -1, -1):
                payload = rect_payloads[index]
                payload_rects = self._payload_rects(payload)
                if any(bounds.inflate(2, 2).colliderect(existing_rect) for existing_rect in payload_rects):
                    grouped_payloads.extend(
                        [
                            [existing_rect.x, existing_rect.y, existing_rect.width, existing_rect.height]
                            for existing_rect in payload_rects
                        ]
                    )
                    for existing_rect in payload_rects:
                        bounds.union_ip(existing_rect)
                    del rect_payloads[index]
                    merged_count += 1
                    changed = True

        rect_payloads.append(cast("list[int]", grouped_payloads))
        return bounds, merged_count

    def _remove_nearest_item(self, world_pos: tuple[int, int]) -> None:
        """Remove the nearest item from the current tool layer."""
        if self.tool in RESOURCE_TOOLS:
            removed = self._remove_nearest_point(self._resource_list(self.tool), world_pos, dimensions=2)
        elif self.tool in POINT_TERRAIN_TOOLS:
            removed = self._remove_nearest_point(self._terrain_list(self.tool), world_pos, dimensions=3)
        elif self.tool in RECT_TERRAIN_TOOLS:
            removed = self._remove_rect_at(self._terrain_list(self.tool), world_pos)
        elif self.tool in ENTITY_TOOLS:
            removed = self._remove_nearest_point(self._team_entity_list(self.tool), world_pos, dimensions=2)
        else:
            removed = False

        self.status = f"Removed {self.tool}" if removed else f"No {self.tool} nearby"

    def _erase_area_or_point(self, rect: pygame.Rect, world_pos: tuple[int, int]) -> None:
        """Erase any map asset at a point or inside a dragged area.

        This is intentionally broader than right-click layer deletion: it can
        remove resources, decorations, team entities, and terrain groups without
        switching tools.
        """
        if rect.width < 8 and rect.height < 8:
            removed = self._remove_any_nearest(world_pos)
        else:
            removed = self._remove_any_in_rect(rect)
        self.status = f"Erased {removed} item(s)" if removed else "Nothing to erase"

    def _flatten_area_or_point(self, rect: pygame.Rect, world_pos: tuple[int, int]) -> None:
        """Remove terrain regions from a point or dragged area.

        Flattening is a terrain-only eraser. It removes ``high_ground``,
        ``ramps``, and ``water`` groups/rectangles while leaving placed entities,
        resource nodes, rocks, and grass untouched.
        """
        if rect.width < 8 and rect.height < 8:
            removed = sum(self._remove_rect_at(self._terrain_list(key), world_pos) for key in RECT_TERRAIN_TOOLS)
        else:
            removed = sum(self._remove_rects_intersecting(self._terrain_list(key), rect) for key in RECT_TERRAIN_TOOLS)
        self.status = f"Flattened {removed} terrain region(s)" if removed else "No terrain to flatten"

    def _remove_any_nearest(self, world_pos: tuple[int, int]) -> int:
        """Remove the nearest point asset or topmost terrain rectangle."""
        for key in RECT_TERRAIN_TOOLS:
            if self._remove_rect_at(self._terrain_list(key), world_pos):
                return 1

        candidates: list[tuple[float, list[list[int]], int]] = []
        for key in RESOURCE_TOOLS:
            self._collect_nearest_candidate(candidates, self._resource_list(key), world_pos, dimensions=2)
        for key in POINT_TERRAIN_TOOLS:
            self._collect_nearest_candidate(candidates, self._terrain_list(key), world_pos, dimensions=3)
        for entity_list in self._existing_team_entity_lists():
            self._collect_nearest_candidate(candidates, entity_list, world_pos, dimensions=2)

        if not candidates:
            return 0

        _, payloads, index = min(candidates, key=lambda candidate: candidate[0])
        del payloads[index]
        return 1

    def _remove_any_in_rect(self, rect: pygame.Rect) -> int:
        """Remove all assets contained in a dragged rectangle."""
        removed = 0
        for key in RECT_TERRAIN_TOOLS:
            removed += self._remove_rects_intersecting(self._terrain_list(key), rect)
        for key in RESOURCE_TOOLS:
            removed += self._remove_points_in_rect(self._resource_list(key), rect)
        for key in POINT_TERRAIN_TOOLS:
            removed += self._remove_points_in_rect(self._terrain_list(key), rect)
        for entity_list in self._existing_team_entity_lists():
            removed += self._remove_points_in_rect(entity_list, rect)
        return removed

    def _existing_team_entity_lists(self) -> list[list[list[int]]]:
        """Return existing team entity lists without creating new JSON keys."""
        entity_lists: list[list[list[int]]] = []
        for team_name in ("Blue", "Red"):
            team_settings = self.settings.get(team_name, {})
            if not isinstance(team_settings, dict):
                continue
            for points in team_settings.values():
                if isinstance(points, list):
                    entity_lists.append(cast("list[list[int]]", points))
        return entity_lists

    @staticmethod
    def _collect_nearest_candidate(
        candidates: list[tuple[float, list[list[int]], int]],
        payloads: list[list[int]],
        world_pos: tuple[int, int],
        *,
        dimensions: int,
    ) -> None:
        """Collect a nearest-removal candidate from point payloads."""
        for index, payload in enumerate(payloads):
            if len(payload) < dimensions:
                continue
            distance = ((payload[0] - world_pos[0]) ** 2 + (payload[1] - world_pos[1]) ** 2) ** 0.5
            if distance < DELETE_DISTANCE:
                candidates.append((distance, payloads, index))

    def _remove_nearest_point(
        self,
        points: list[list[int]],
        world_pos: tuple[int, int],
        *,
        dimensions: int,
    ) -> bool:
        """Remove the nearest point-like payload from a list."""
        best_index = -1
        best_distance = DELETE_DISTANCE
        for index, payload in enumerate(points):
            if len(payload) < dimensions:
                continue
            distance = ((payload[0] - world_pos[0]) ** 2 + (payload[1] - world_pos[1]) ** 2) ** 0.5
            if distance < best_distance:
                best_index = index
                best_distance = distance
        if best_index < 0:
            return False
        del points[best_index]
        return True

    @staticmethod
    def _remove_rect_at(rect_payloads: list[list[int]], world_pos: tuple[int, int]) -> bool:
        """Remove the topmost rectangle containing a point."""
        for index in range(len(rect_payloads) - 1, -1, -1):
            payload = rect_payloads[index]
            if any(rect.collidepoint(world_pos) for rect in MapEditor._payload_rects(payload)):
                del rect_payloads[index]
                return True
        return False

    @staticmethod
    def _remove_rects_intersecting(rect_payloads: list[list[int]], rect: pygame.Rect) -> int:
        """Remove rectangles intersecting a selection rectangle."""
        removed = 0
        for index in range(len(rect_payloads) - 1, -1, -1):
            payload = rect_payloads[index]
            if any(payload_rect.colliderect(rect) for payload_rect in MapEditor._payload_rects(payload)):
                del rect_payloads[index]
                removed += 1
        return removed

    @staticmethod
    def _payload_rects(payload: object) -> list[pygame.Rect]:
        """Return all rectangles represented by a flat or nested terrain payload.

        This mirrors ``TerrainMap`` parsing so editor operations work on both
        canonical grouped terrain and older flat rectangles. Editor saves will
        normalize the result.
        """
        if MapEditor._is_rect_payload(payload):
            return [pygame.Rect(*cast("list[int]", payload))]
        if not isinstance(payload, list):
            return []
        return [pygame.Rect(*cast("list[int]", item)) for item in payload if MapEditor._is_rect_payload(item)]

    @staticmethod
    def _is_rect_payload(payload: object) -> bool:
        """Return whether payload is [x, y, width, height]."""
        return isinstance(payload, list) and len(payload) == 4 and all(isinstance(value, int) for value in payload)

    @staticmethod
    def _remove_points_in_rect(payloads: list[list[int]], rect: pygame.Rect) -> int:
        """Remove point-like payloads contained in a selection rectangle."""
        removed = 0
        for index in range(len(payloads) - 1, -1, -1):
            payload = payloads[index]
            if len(payload) >= 2 and rect.collidepoint(payload[0], payload[1]):
                del payloads[index]
                removed += 1
        return removed

    @staticmethod
    def _normalized_rect(start: tuple[int, int], end: tuple[int, int]) -> pygame.Rect:
        """Build a positive-size rectangle from two world points."""
        left = min(start[0], end[0])
        top = min(start[1], end[1])
        width = abs(end[0] - start[0])
        height = abs(end[1] - start[1])
        return pygame.Rect(left, top, width, height)

    def _draw_grid(self, screen: pygame.Surface) -> None:
        """Draw the editor grid."""
        start_x = -(self.camera_x % GRID_SIZE)
        start_y = -(self.camera_y % GRID_SIZE)
        for x in range(int(start_x), SCREEN_WIDTH, GRID_SIZE):
            pygame.draw.line(screen, (58, 80, 55), (x, 0), (x, screen.get_height()))
        for y in range(int(start_y), screen.get_height(), GRID_SIZE):
            pygame.draw.line(screen, (58, 80, 55), (0, y), (SCREEN_WIDTH, y))

    def _draw_resources(self, screen: pygame.Surface) -> None:
        """Draw resource markers."""
        resources = self.settings.get("Resources", {})
        if not isinstance(resources, dict):
            return
        resources_payload = cast("dict[str, object]", resources)
        wood_points = resources_payload.get("wood", [])
        if not isinstance(wood_points, list):
            wood_points = []
        for point in wood_points:
            if not isinstance(point, list):
                continue
            pygame.draw.circle(screen, (35, 25, 18), self._world_to_screen(cast("Sequence[int]", point)), 6)
        gold_points = resources_payload.get("gold", [])
        if not isinstance(gold_points, list):
            gold_points = []
        for point in gold_points:
            if not isinstance(point, list):
                continue
            pygame.draw.circle(screen, (255, 215, 0), self._world_to_screen(cast("Sequence[int]", point)), 6)

    def _draw_entities(self, screen: pygame.Surface) -> None:
        """Draw simple team/entity markers."""
        team_colors = {"Blue": BLUE, "Red": RED}
        for team_name, color in team_colors.items():
            team_settings = self.settings.get(team_name, {})
            if not isinstance(team_settings, dict):
                continue
            for entity_name, points in team_settings.items():
                if not isinstance(points, list):
                    continue
                for point in points:
                    if not isinstance(point, list):
                        continue
                    pos = self._world_to_screen(cast("Sequence[int]", point))
                    size = (
                        24
                        if entity_name in {"base", "house", "arsenal", "spire", "bastion", "pit", "chem_vat", "spiker"}
                        else 12
                    )
                    rect = pygame.Rect(0, 0, size, size)
                    rect.center = pos
                    pygame.draw.rect(screen, color, rect, width=2)
                    pygame.draw.line(screen, color, (pos[0] - 5, pos[1]), (pos[0] + 5, pos[1]), 1)
                    pygame.draw.line(screen, color, (pos[0], pos[1] - 5), (pos[0], pos[1] + 5), 1)

    def _draw_pending_rect(self, screen: pygame.Surface) -> None:
        """Draw the rectangle currently being dragged."""
        if self.drag_start is None or self.drag_current is None:
            return
        rect = self._normalized_rect(
            self._world_to_screen(self.drag_start),
            self._world_to_screen(self.drag_current),
        )
        pygame.draw.rect(screen, YELLOW, rect, width=2)

    def _draw_hud(self, screen: pygame.Surface) -> None:
        """Draw editor controls and status."""
        hud_rect = pygame.Rect(0, SCREEN_HEIGHT - HUD_HEIGHT, SCREEN_WIDTH, HUD_HEIGHT)
        pygame.draw.rect(screen, (28, 28, 28), hud_rect)
        pygame.draw.rect(screen, WHITE, hud_rect, width=2)

        font = pygame.font.SysFont(None, 24)
        small_font = pygame.font.SysFont(None, 20)
        mouse_world = self._screen_to_world(pygame.mouse.get_pos())
        header = (
            f"Tool: {TOOL_LABELS.get(self.tool, self.tool)} | "
            f"Mouse: {mouse_world[0]},{mouse_world[1]} | "
            f"Snap: {'ON' if self.snap_to_grid else 'OFF'} | "
            "Ctrl+S save | Ctrl+O load next | Ctrl+N new | Arrows/edge move camera"
        )
        screen.blit(font.render(header, True, WHITE), (12, SCREEN_HEIGHT - HUD_HEIGHT + 10))
        screen.blit(small_font.render(self.status, True, YELLOW), (12, SCREEN_HEIGHT - HUD_HEIGHT + 36))

        labels = " | ".join(TOOL_LABELS.values())
        screen.blit(small_font.render(labels, True, (210, 210, 210)), (12, SCREEN_HEIGHT - HUD_HEIGHT + 62))


def _parse_args() -> Namespace:
    """Parse map editor CLI arguments.

    Bare filenames are resolved under ``src/rts_nano/maps``. Paths with a parent
    component are treated as explicit relative/absolute paths so temporary files
    and external map folders remain possible.
    """
    parser = ArgumentParser(description="RTS Nano map editor")
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP_PATH, help="Map JSON file to load.")
    parser.add_argument("--new", type=Path, help="Create a new blank map at this path and open it.")
    parser.add_argument("--width", type=int, default=3200, help="Width for --new maps.")
    parser.add_argument("--height", type=int, default=2200, help="Height for --new maps.")
    parser.add_argument("--overwrite", action="store_true", help="Allow --new to overwrite an existing file.")
    return parser.parse_args()


def _resolve_map_path(path: Path) -> Path:
    """Resolve a map path, treating bare filenames as maps-directory entries."""
    if path.is_absolute() or path.parent != Path():
        return path
    return MAPS_DIR / path


def _editor_from_args(args: Namespace) -> MapEditor:
    """Create an editor from command-line arguments."""
    if args.new:
        map_path = _resolve_map_path(args.new)
        if map_path.exists() and not args.overwrite:
            raise FileExistsError(f"{map_path} already exists. Use --overwrite to replace it.")
        editor = MapEditor(DEFAULT_MAP_PATH)
        editor.create_new_map(map_path, width=args.width, height=args.height)
        return editor

    return MapEditor(_resolve_map_path(args.map))


def main() -> None:
    """Run the standalone map editor."""
    args = _parse_args()
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("RTS Nano Map Editor")
    clock = pygame.time.Clock()
    editor = _editor_from_args(args)

    running = True
    while running:
        for event in pygame.event.get():
            running = editor.handle_event(event)
            if not running:
                break

        editor.update()
        screen.fill(BLACK)
        editor.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
