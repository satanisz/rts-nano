"""Game state coordination, input handling, simulation, and rendering.

``GameManager`` is the central runtime object for the playable game. It owns the
loaded map, all entities, camera state, selected units, transient VFX, resource
collection, combat projectiles, HUD widgets, and the F10 menu. The outer
``main.py`` loop owns only pygame display creation and process-level events.

Coordinate model:

* entities, terrain, resources, paths, and orders use world coordinates,
* the camera is stored as ``camera_x/camera_y`` and subtracted only for drawing,
* mouse events arrive in screen coordinates and are converted before world
  interaction,
* the bottom UI panel and minimap are screen-space overlays.

Simulation model:

* units update themselves, but the manager supplies terrain movement validation,
* peasants use manager-level harvesting/deposit logic because it touches team
  resources and neutral resource lists,
* ranged unit attacks emit events consumed here to spawn projectile VFX,
* dead entities are pruned after all entity updates for the frame.

When adding features, keep the split clear: entity classes own per-entity state
machines, ``TerrainMap`` owns terrain queries, and this manager coordinates
cross-entity systems.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import pygame

from rts_nano.game.assets.entities import Archer, Base, Cristal, Knight, Mage, Peasant, TeamColor, Wood
from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, Unit
from rts_nano.game.constants import (
    BLACK,
    BLUE,
    BOTTOM_MENU_HEIGHT,
    CYAN,
    GREEN,
    HARVEST_SEARCH_RADIUS,
    MAX_UNITS,
    RED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE,
    AttackType,
)
from rts_nano.game.pathfinding import find_path
from rts_nano.game.rules import clamp_point, distance_between_points, find_replacement_resource, nearest_entity
from rts_nano.game.terrain import TerrainMap

if TYPE_CHECKING:
    from collections.abc import Callable

    from rts_nano.map_schema import MapSettings

WOOD_ICON = "\U0001fab5"
CRISTAL_ICON = "\U0001f48e"
FULLSCREEN_TOGGLE_EVENT = pygame.USEREVENT + 1
PLAY_AREA_HEIGHT = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT
CAMERA_SPEED = 12
EDGE_SCROLL_MARGIN = 24
MINIMAP_WIDTH = 220
MINIMAP_HEIGHT = 150
MINIMAP_PADDING = 12


@dataclass
class MagicMissile:
    """Visual projectile effect used for mage ranged attacks.

    The projectile is cosmetic. Damage is applied by ``Unit._attack`` before the
    event reaches the manager. If ``target_entity`` is still alive, the missile
    homes toward its current center so moving targets look natural.
    """

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
        dist = math.sqrt(dx**2 + dy**2)

        if dist <= self.speed or dist == 0:
            self.x = self.target_x
            self.y = self.target_y
            return False

        self.x += (dx / dist) * self.speed
        self.y += (dy / dist) * self.speed
        return True

    def draw(self, screen: pygame.Surface, offset: tuple[float, float] = (0, 0)) -> None:
        """Render a bright core with a soft glow for readability."""
        offset_x, offset_y = offset
        draw_pos = (int(self.x - offset_x), int(self.y - offset_y))
        pygame.draw.circle(screen, (120, 235, 255), draw_pos, self.radius + 3)
        pygame.draw.circle(screen, CYAN, draw_pos, self.radius)
        pygame.draw.circle(screen, WHITE, draw_pos, 2)


@dataclass
class ArcherShot:
    """Visual projectile effect used for archer ranged attacks.

    Like ``MagicMissile``, this object does not apply damage. It exists only to
    make an already-resolved ranged attack visible to the player.
    """

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
        dist = math.sqrt(dx**2 + dy**2)

        if dist <= self.speed or dist == 0:
            self.x = self.target_x
            self.y = self.target_y
            return False

        self.x += (dx / dist) * self.speed
        self.y += (dy / dist) * self.speed
        return True

    def draw(self, screen: pygame.Surface, offset: tuple[float, float] = (0, 0)) -> None:
        """Render a dark arrow-like bolt with a subtle trail."""
        offset_x, offset_y = offset
        draw_pos = (int(self.x - offset_x), int(self.y - offset_y))
        pygame.draw.circle(screen, (70, 70, 70), draw_pos, self.radius + 2)
        pygame.draw.circle(screen, BLACK, draw_pos, self.radius)


@dataclass
class ClickMarker:
    """Short-lived visual marker for issued map orders.

    Markers are stored in world coordinates and drawn with the same camera
    offset as entities. They are intentionally independent of selected units:
    even a right click with no units selected confirms where the player clicked.
    """

    x: float
    y: float
    color: tuple[int, int, int]
    created_at_ms: int
    duration_ms: int = 450

    def is_alive(self, now_ms: int) -> bool:
        """Return whether this marker should still be drawn."""
        return now_ms - self.created_at_ms < self.duration_ms

    def draw(self, screen: pygame.Surface, offset: tuple[float, float] = (0, 0)) -> None:
        """Draw an expanding ring at the order position."""
        now_ms = pygame.time.get_ticks()
        elapsed = now_ms - self.created_at_ms
        progress = min(max(elapsed / self.duration_ms, 0.0), 1.0)
        alpha = int(220 * (1.0 - progress))
        radius = int(8 + progress * 22)
        offset_x, offset_y = offset
        draw_pos = (int(self.x - offset_x), int(self.y - offset_y))

        marker_surface = pygame.Surface((radius * 2 + 6, radius * 2 + 6), pygame.SRCALPHA)
        center = marker_surface.get_width() // 2, marker_surface.get_height() // 2
        color = (*self.color, alpha)
        pygame.draw.circle(marker_surface, color, center, radius, width=3)
        pygame.draw.line(marker_surface, color, (center[0] - 6, center[1]), (center[0] + 6, center[1]), width=2)
        pygame.draw.line(marker_surface, color, (center[0], center[1] - 6), (center[0], center[1] + 6), width=2)
        screen.blit(marker_surface, marker_surface.get_rect(center=draw_pos))


class EntitiesGroup:
    """Store team-owned entities and collected resources.

    The map JSON groups entities by team, but the runtime further separates unit
    classes into lists for simple counts, UI summaries, and production logic.
    Neutral resources are not stored here; they live in ``ResourcesGroup``.

    Args:
        name: Team associated with the entity collection.
    """

    def __init__(self, name: TeamColor) -> None:
        """Initialize the object."""
        self.name: TeamColor = name
        self.resources: dict[str, int] = {"wood": 0, "cristal": 0}
        self.bases: list[Base] = []
        self.peasents: list[Peasant] = []
        self.knights: list[Knight] = []
        self.archers: list[Archer] = []
        self.mages: list[Mage] = []

    @property
    def all_entities(self) -> list[Entity]:
        """Return all entities owned by the team."""
        all_ents: list[Entity] = []
        all_ents.extend(self.bases)
        all_ents.extend(self.peasents)
        all_ents.extend(self.knights)
        all_ents.extend(self.archers)
        all_ents.extend(self.mages)
        return all_ents


class ResourcesGroup:
    """Store neutral resource nodes available on the map.

    Resources are normal entities for drawing/selection/collision, but their
    lifetime differs from units: they disappear when ``amount`` reaches zero
    rather than when ``life`` reaches zero.
    """

    def __init__(self) -> None:
        """Initialize the object."""
        self.cristals: list[Cristal] = []
        self.woods: list[Wood] = []


class EntityFactory:
    """Create game entities from map configuration values.

    The factory is the only place that maps serialized asset names such as
    ``"peasant"`` or ``"cristal"`` to concrete classes. Add new JSON entity
    types here before expecting maps or the editor to spawn them in-game.
    """

    _TEAM_ENTITY_TYPES: dict[str, Callable[[int, int, TeamColor], Entity]] = {
        "peasant": Peasant,
        "knight": Knight,
        "archer": Archer,
        "mage": Mage,
        "base": Base,
    }
    _NEUTRAL_ENTITY_TYPES: dict[str, Callable[[int, int], Entity]] = {
        "wood": Wood,
        "cristal": Cristal,
    }

    @classmethod
    def create_entity(cls, asset_type: str, x: int, y: int, team: TeamColor) -> Entity:
        """Create an entity instance matching the requested asset type.

        Args:
            asset_type: Serialized concrete asset type name.
            x: Horizontal spawn position.
            y: Vertical spawn position.
            team: Team associated with the entity.

        Returns:
            Instantiated entity.

        Raises:
            ValueError: If the asset type is unknown.
        """
        team_entity_type = cls._TEAM_ENTITY_TYPES.get(asset_type)
        if team_entity_type is not None:
            return team_entity_type(x, y, team)

        neutral_entity_type = cls._NEUTRAL_ENTITY_TYPES.get(asset_type)
        if neutral_entity_type is not None:
            return neutral_entity_type(x, y)

        raise ValueError(f"Unknown asset type: {asset_type}")


class GameManager:
    """Coordinate input, simulation, selection, and drawing.

    Args:
        map_settings: Parsed JSON map settings. Team sections are dictionaries
            of entity type to coordinate list. The ``Terrain`` section is passed
            directly to ``TerrainMap``.

    Important invariants:
        ``map_width``/``map_height`` describe the world bounds. ``SCREEN_WIDTH``
        and ``SCREEN_HEIGHT`` are updated by ``set_viewport_size`` so existing
        rendering helpers can still use module-level constants. New gameplay
        logic should prefer helper methods such as ``_screen_to_world`` and
        ``_clamp_to_world`` instead of reading camera fields directly.
    """

    def __init__(self, map_settings: MapSettings) -> None:
        """Initialize the object."""
        self.map_settings = map_settings
        self.terrain = TerrainMap(map_settings.get("Terrain"))
        self.entities: dict[TeamColor, EntitiesGroup] = {}
        self.resources: ResourcesGroup = ResourcesGroup()
        self.selected_entities: list[Entity] = []
        self.current_team: TeamColor = TeamColor.BLUE
        self.dragging: bool = False
        self.minimap_dragging: bool = False
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
        self.paused: bool = False
        self.menu_active: bool = False
        self.fullscreen_enabled: bool = False
        self.fps_multiplier: float = 1.0
        self.menu_options: list[str] = [
            "CONTINUE",
            "SAVE",
            "LOAD",
            "SPEED: NORMAL",
            "FULLSCREEN: OFF",
            "EXIT",
        ]
        self.magic_missiles: list[MagicMissile] = []
        self.archer_shots: list[ArcherShot] = []
        self.click_markers: list[ClickMarker] = []
        self.build_peasant_buttons: list[tuple[pygame.Rect, Base]] = []
        self.game_over_message: str | None = None
        self.menu_status: str | None = None
        self.mouse_pos: tuple[int, int] = (0, 0)
        self.camera_x: float = 0
        self.camera_y: float = 0
        self.map_width = max(self.terrain.width, SCREEN_WIDTH)
        self.map_height = max(self.terrain.height, PLAY_AREA_HEIGHT)

        self._load_map_settings()
        self.set_viewport_size(SCREEN_WIDTH, SCREEN_HEIGHT)

    def set_viewport_size(self, width: int, height: int) -> None:
        """Update the visible game area to match the current display size.

        The project originally used fixed screen constants. Fullscreen/window
        work made the viewport dynamic, so this method mutates the module-level
        ``SCREEN_WIDTH``, ``SCREEN_HEIGHT``, and ``PLAY_AREA_HEIGHT`` imported
        from constants. This is intentionally centralized; avoid changing those
        globals elsewhere.
        """
        global PLAY_AREA_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH

        SCREEN_WIDTH = max(1, int(width))
        SCREEN_HEIGHT = max(BOTTOM_MENU_HEIGHT + 1, int(height))
        PLAY_AREA_HEIGHT = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT
        self.map_width = max(self.terrain.width, SCREEN_WIDTH)
        self.map_height = max(self.terrain.height, PLAY_AREA_HEIGHT)
        self._clamp_camera()

    def _remove_dead_entities(self) -> None:
        """Remove defeated units and buildings from the game state."""
        removed_entities: set[int] = set()

        for group in self.entities.values():
            for attr_name in ("peasents", "knights", "archers", "mages", "bases"):
                entities = getattr(group, attr_name)
                alive_entities = [entity for entity in entities if entity.life > 0]
                removed_entities.update(id(entity) for entity in entities if entity.life <= 0)
                setattr(group, attr_name, alive_entities)

        if removed_entities:
            self.selected_entities = [entity for entity in self.selected_entities if id(entity) not in removed_entities]

    @property
    def all_entities(self) -> list[Entity]:
        """Return all active entities, including units, buildings, and resources."""
        ents = [entity for group in self.entities.values() for entity in group.all_entities]
        ents.extend(self.resources.woods)
        ents.extend(self.resources.cristals)
        return ents

    def _count_units(self, team: TeamColor) -> int:
        """Return the number of living units owned by a team."""
        group = self.entities.get(team)
        if group is None:
            return 0
        return len(group.peasents) + len(group.knights) + len(group.archers) + len(group.mages)

    def _has_reached_unit_cap(self, team: TeamColor) -> bool:
        """Return whether a team is at the current unit cap."""
        return self._count_units(team) >= MAX_UNITS

    def _clamp_to_world(self, pos: tuple[float, float]) -> tuple[int, int]:
        """Clamp a world-space point to map bounds.

        Use this for orders, spawned units, path goals, and converted mouse
        coordinates. It clamps to full map dimensions, not to the visible
        viewport.
        """
        x, y = clamp_point(pos, min_x=0, max_x=self.map_width, min_y=0, max_y=self.map_height)
        return int(x), int(y)

    def _clamp_camera(self) -> None:
        """Keep the viewport inside the map."""
        self.camera_x = min(max(self.camera_x, 0), max(0, self.map_width - SCREEN_WIDTH))
        self.camera_y = min(max(self.camera_y, 0), max(0, self.map_height - PLAY_AREA_HEIGHT))

    def _screen_to_world(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Convert a screen point in the play area to world coordinates.

        This helper assumes ``pos`` is in the game's current display coordinate
        system, not desktop coordinates. ``main.py`` renders directly to the
        display surface, so no additional scale transform is needed.
        """
        return self._clamp_to_world((pos[0] + self.camera_x, pos[1] + self.camera_y))

    def _world_to_screen(self, pos: tuple[float, float]) -> tuple[int, int]:
        """Convert world coordinates to screen coordinates."""
        return int(pos[0] - self.camera_x), int(pos[1] - self.camera_y)

    def _minimap_rect(self) -> pygame.Rect:
        """Return the screen rectangle used by the minimap."""
        return pygame.Rect(
            MINIMAP_PADDING,
            SCREEN_HEIGHT - MINIMAP_HEIGHT - MINIMAP_PADDING,
            MINIMAP_WIDTH,
            MINIMAP_HEIGHT,
        )

    def _center_camera_on_world_pos(self, pos: tuple[float, float]) -> None:
        """Center the viewport on a world point."""
        self.camera_x = pos[0] - SCREEN_WIDTH / 2
        self.camera_y = pos[1] - PLAY_AREA_HEIGHT / 2
        self._clamp_camera()

    def _center_camera_from_minimap_pos(self, pos: tuple[int, int]) -> None:
        """Center the viewport from a minimap screen point."""
        minimap_rect = self._minimap_rect()
        mini_x = min(max(pos[0], minimap_rect.left), minimap_rect.right)
        mini_y = min(max(pos[1], minimap_rect.top), minimap_rect.bottom)
        world_x = (mini_x - minimap_rect.left) / minimap_rect.width * self.map_width
        world_y = (mini_y - minimap_rect.top) / minimap_rect.height * self.map_height
        self._center_camera_on_world_pos((world_x, world_y))

    def set_mouse_pos(self, pos: tuple[int, int]) -> None:
        """Store the current logical mouse position."""
        self.mouse_pos = pos

    def _update_game_over_state(self) -> None:
        """Detect a simple elimination victory condition."""
        active_teams = [
            team
            for team, group in self.entities.items()
            if team != TeamColor.RESOURCES and any(entity.life > 0 for entity in group.all_entities)
        ]
        if len(active_teams) == 1:
            self.game_over_message = f"Team {active_teams[0].value} wins"
            self.paused = True
        elif not active_teams:
            self.game_over_message = "Draw"
            self.paused = True

    def _update_entity_height_levels(self) -> None:
        """Refresh entity height levels from the terrain map."""
        for entity in self.all_entities:
            entity.height_level = self.terrain.height_at(entity.get_center())

    def _can_unit_move_to(self, unit: Unit, next_point: tuple[float, float]) -> bool:
        """Return whether terrain permits a unit movement step."""
        next_x, next_y = self._clamp_to_world(next_point)
        return self.terrain.can_move_between(unit.get_center(), (next_x, next_y), radius=unit.radius)

    def _find_unit_path(self, unit: Unit, destination: tuple[float, float]) -> list[tuple[float, float]]:
        """Build a terrain-aware path for a unit."""
        goal = self._clamp_to_world(destination)
        return find_path(
            unit.get_center(),
            goal,
            width=self.map_width,
            height=self.map_height,
            can_move_between=lambda current, next_point: self.terrain.can_move_between(
                current,
                next_point,
                radius=unit.radius,
            ),
        )

    def _assign_unit_target(
        self,
        unit: Unit,
        destination: tuple[float, float],
        target_entity: Entity | None = None,
    ) -> None:
        """Assign a unit target plus an A* path when one is available."""
        unit.set_target(destination, target_entity)
        unit.set_path(self._find_unit_path(unit, destination))

    def _load_map_settings(self) -> None:
        """Instantiate entities from the loaded map configuration.

        Every non-``Terrain`` top-level key is interpreted as a ``TeamColor``.
        This currently includes ``Blue``, ``Red``, and ``Resources``. Resource
        entities are created while iterating the resources group but stored in
        ``self.resources`` rather than the temporary group.
        """
        for category_str, assets in self.map_settings.items():
            if category_str == "Terrain":
                continue
            if not isinstance(assets, dict):
                raise TypeError(f"Invalid map category payload: {category_str!r}")
            team_color = TeamColor(category_str)
            group = EntitiesGroup(team_color)
            self.entities[team_color] = group

            for asset_type, coords in assets.items():
                normalized_coords = self._normalize_coords(coords)
                for x, y in normalized_coords:
                    entity = EntityFactory.create_entity(cast("str", asset_type), x, y, team_color)
                    match entity:
                        case Peasant():
                            group.peasents.append(entity)
                        case Knight():
                            group.knights.append(entity)
                        case Archer():
                            group.archers.append(entity)
                        case Mage():
                            group.mages.append(entity)
                        case Base():
                            group.bases.append(entity)
                        case Wood():
                            self.resources.woods.append(entity)
                        case Cristal():
                            self.resources.cristals.append(entity)

    def _normalize_coords(self, coords: object) -> list[tuple[int, int]]:
        """Normalize map coordinates to a list of coordinate pairs."""
        if not isinstance(coords, list):
            raise TypeError(f"Invalid coordinate payload: {coords!r}")
        if len(coords) == 2 and all(isinstance(value, (int, float)) for value in coords):
            return [self._coerce_coord_pair(coords)]
        return [self._coerce_coord_pair(coord_pair) for coord_pair in coords]

    @staticmethod
    def _coerce_coord_pair(coord_pair: object) -> tuple[int, int]:
        """Convert one JSON coordinate pair to integer screen coordinates."""
        match coord_pair:
            case [int() | float() as x, int() | float() as y]:
                return int(x), int(y)
            case (int() | float() as x, int() | float() as y):
                return int(x), int(y)
        raise TypeError(f"Invalid coordinate pair: {coord_pair!r}")

    def handle_input(self, event: pygame.event.Event) -> None:
        """Process keyboard and mouse input for team control and selection.

        Mouse handling is split into three screen-space zones:

        * F10 menu consumes all clicks while active,
        * minimap consumes left clicks/drag before world selection,
        * bottom panel blocks world orders and hosts build buttons.

        World interactions convert to world coordinates immediately. Selection
        rectangles store world coordinates so dragging remains correct while the
        camera is moving.

        Args:
            event: Pygame event to process.
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                if self.current_team == TeamColor.BLUE:
                    self.current_team = TeamColor.RED
                else:
                    self.current_team = TeamColor.BLUE
                for entity in self.selected_entities:
                    entity.selected = False
                self.selected_entities.clear()
            elif event.key == pygame.K_q:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            elif event.key == pygame.K_p:
                if not self.menu_active:
                    self.paused = not self.paused
            elif event.key == pygame.K_F10:
                self.menu_active = not self.menu_active
                self.paused = self.menu_active
            elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
                self._request_fullscreen_toggle()
            elif event.key == pygame.K_b:
                self._try_build_peasant_from_selection()

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            self.set_mouse_pos(mouse_pos)

            if self.menu_active:
                if event.button == 1:
                    self._handle_menu_click(mouse_pos)
                return  # Block world interaction while menu is open

            if event.button == 1:
                minimap_rect = self._minimap_rect()
                if minimap_rect.collidepoint(mouse_pos):
                    self.minimap_dragging = True
                    self._center_camera_from_minimap_pos(mouse_pos)
                    return

                # Check UI buttons first
                for rect, base in self.build_peasant_buttons:
                    if rect.collidepoint(mouse_pos):
                        self._build_peasant(base)
                        return
                if mouse_pos[1] >= PLAY_AREA_HEIGHT:
                    return

                self.dragging = True
                world_pos = self._screen_to_world(mouse_pos)
                self.drag_start = world_pos
                self.drag_end = world_pos

            elif event.button == 3:
                if mouse_pos[1] >= PLAY_AREA_HEIGHT:
                    return
                order_pos = self._screen_to_world(mouse_pos)
                if self.terrain.blocks_movement(order_pos):
                    return
                target_entity = None
                for entity in self.all_entities:
                    if entity.contains_point(order_pos):
                        target_entity = entity
                        break

                marker_color = (255, 80, 80) if target_entity else (80, 255, 120)
                self.click_markers.append(
                    ClickMarker(order_pos[0], order_pos[1], marker_color, pygame.time.get_ticks())
                )

                for entity in self.selected_entities:
                    if isinstance(entity, Unit):
                        self._assign_unit_target(entity, order_pos, target_entity)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.minimap_dragging:
                self.minimap_dragging = False
            elif event.button == 1 and self.dragging:
                self.dragging = False
                self.select_units_in_box()
                self.drag_start = None
                self.drag_end = None

        elif event.type == pygame.MOUSEMOTION:
            self.set_mouse_pos(event.pos)
            if self.minimap_dragging:
                self._center_camera_from_minimap_pos(event.pos)
            elif self.dragging:
                self.drag_end = self._screen_to_world(event.pos)

    def _build_peasant(self, base: Base) -> None:
        """Attempt to build a Peasant at the given base."""
        team_group = self.entities.get(base.team)
        if team_group and team_group.resources["wood"] >= 50 and not self._has_reached_unit_cap(base.team):
            team_group.resources["wood"] -= 50
            spawn_x, spawn_y = self._clamp_to_world((base.x, base.y + base.size))
            peasant = Peasant(int(spawn_x), int(spawn_y), base.team)
            team_group.peasents.append(peasant)

    def _try_build_peasant_from_selection(self) -> None:
        """Attempt to build a peasant from the first selected base."""
        for entity in self.selected_entities:
            if isinstance(entity, Base) and entity.team == self.current_team:
                self._build_peasant(entity)
                break

    def _handle_menu_click(self, mouse_pos: tuple[int, int]) -> None:
        """Process clicks on the main menu."""
        menu_width = 300
        button_height = 50
        spacing = 20
        total_height = len(self.menu_options) * (button_height + spacing) - spacing
        start_x = (SCREEN_WIDTH - menu_width) // 2
        start_y = (SCREEN_HEIGHT - total_height) // 2

        for i, option in enumerate(self.menu_options):
            rect = pygame.Rect(start_x, start_y + i * (button_height + spacing), menu_width, button_height)
            if rect.collidepoint(mouse_pos):
                if option == "CONTINUE":
                    self.menu_active = False
                    self.paused = False
                elif option == "SAVE":
                    self.menu_status = "Save is not implemented yet."
                elif option == "LOAD":
                    self.menu_status = "Load is not implemented yet."
                elif option.startswith("SPEED:"):
                    self.menu_status = None
                    if self.fps_multiplier == 1.0:
                        self.fps_multiplier = 2.0
                        self._set_menu_option("SPEED:", "SPEED: FAST")
                    elif self.fps_multiplier == 2.0:
                        self.fps_multiplier = 0.5
                        self._set_menu_option("SPEED:", "SPEED: SLOW")
                    else:
                        self.fps_multiplier = 1.0
                        self._set_menu_option("SPEED:", "SPEED: NORMAL")
                elif option.startswith("FULLSCREEN:"):
                    self._request_fullscreen_toggle()
                elif option == "EXIT":
                    pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _set_menu_option(self, prefix: str, value: str) -> None:
        """Replace the first menu option that starts with prefix."""
        for index, option in enumerate(self.menu_options):
            if option.startswith(prefix):
                self.menu_options[index] = value
                return

    def _request_fullscreen_toggle(self) -> None:
        """Ask the application shell to toggle fullscreen mode."""
        self.set_fullscreen_enabled(not self.fullscreen_enabled)
        pygame.event.post(pygame.event.Event(FULLSCREEN_TOGGLE_EVENT, enabled=self.fullscreen_enabled))

    def set_fullscreen_enabled(self, enabled: bool) -> None:
        """Sync fullscreen state displayed by the menu."""
        self.fullscreen_enabled = enabled
        mode = "ON" if enabled else "OFF"
        self._set_menu_option("FULLSCREEN:", f"FULLSCREEN: {mode}")

    def select_units_in_box(self) -> None:
        """Select units inside the drag rectangle or under the click point.

        Only current-team units can be multi-selected by drag. A click can
        select any entity, including enemies and resources, so the bottom panel
        can inspect them.
        """
        if not self.drag_start or not self.drag_end:
            return

        x1, y1 = self.drag_start
        x2, y2 = self.drag_end
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)

        drag_distance = distance_between_points(self.drag_start, self.drag_end)
        is_click = drag_distance < 5

        for entity in self.all_entities:
            entity.selected = False
        self.selected_entities.clear()

        if is_click:
            for entity in reversed(self.all_entities):
                if entity.contains_point(self.drag_start):
                    entity.selected = True
                    self.selected_entities.append(entity)
                    break
        else:
            for entity in self.all_entities:
                if isinstance(entity, Unit) and entity.team == self.current_team:
                    cx, cy = entity.get_center()
                    if min_x <= cx <= max_x and min_y <= cy <= max_y:
                        entity.selected = True
                        self.selected_entities.append(entity)

    def update(self) -> None:
        """Advance camera, unit simulation, harvesting, combat VFX, and victory.

        The method returns early after camera update when paused. This lets the
        user pan while paused/menu-free, but freezes unit movement, harvesting,
        combat, projectiles, and click marker cleanup.
        """
        self._update_camera()
        if self.paused:
            return

        self._update_entity_height_levels()
        all_ents = self.all_entities
        for entity in all_ents:
            if getattr(entity, "life", 1) <= 0:
                continue

            if isinstance(entity, Unit):
                entity.update(all_ents, self._can_unit_move_to)
                attack_event = entity.consume_attack_event()
                if attack_event and attack_event[2] == AttackType.RANGED:
                    source_pos, target_pos, _, target_entity = attack_event
                    if isinstance(entity, Mage):
                        self.magic_missiles.append(
                            MagicMissile(
                                source_pos[0],
                                source_pos[1],
                                target_pos[0],
                                target_pos[1],
                                target_entity=target_entity,
                            )
                        )
                    elif isinstance(entity, Archer):
                        source_pos, target_pos, _, target_entity = attack_event
                        self.archer_shots.append(
                            ArcherShot(
                                source_pos[0],
                                source_pos[1],
                                target_pos[0],
                                target_pos[1],
                                target_entity=target_entity,
                            )
                        )

            if isinstance(entity, Peasant):
                if entity.state == "GATHERING":
                    resource = entity.target_entity or entity.source_resource
                    if isinstance(resource, (Wood, Cristal)):
                        is_wood = isinstance(resource, Wood)

                        if resource.amount > 0:
                            gathered = min(1, resource.amount)
                            resource.amount -= gathered

                            if is_wood:
                                entity.carry_wood += gathered
                            else:
                                entity.carry_cristal += gathered

                            if resource.amount <= 0:
                                if isinstance(resource, Wood) and resource in self.resources.woods:
                                    self.resources.woods.remove(resource)
                                elif isinstance(resource, Cristal) and resource in self.resources.cristals:
                                    self.resources.cristals.remove(resource)

                                resource_list = self.resources.woods if is_wood else self.resources.cristals
                                new_resource = find_replacement_resource(
                                    resource,
                                    resource_list,
                                    search_radius=HARVEST_SEARCH_RADIUS,
                                )
                                entity.source_resource = new_resource
                                entity.target_entity = new_resource

                        carry_amount = entity.carry_wood if is_wood else entity.carry_cristal
                        if carry_amount >= entity.max_carry or resource.amount <= 0:
                            if is_wood and entity.carry_wood > entity.max_carry:
                                entity.carry_wood = entity.max_carry
                            elif not is_wood and entity.carry_cristal > entity.max_carry:
                                entity.carry_cristal = entity.max_carry

                            team_group = self.entities.get(entity.team)
                            team_bases = team_group.bases if team_group else []
                            nearest_base = nearest_entity(entity, team_bases)
                            if nearest_base:
                                self._assign_unit_target(entity, nearest_base.get_center(), nearest_base)
                            else:
                                entity.state = "IDLE"

                elif entity.state == "DEPOSITING":
                    team_group = self.entities.get(entity.team)
                    if team_group:
                        team_group.resources["wood"] += entity.carry_wood
                        team_group.resources["cristal"] += entity.carry_cristal
                    entity.carry_wood = 0
                    entity.carry_cristal = 0
                    if (
                        entity.source_resource
                        and entity.source_resource in all_ents
                        and entity.source_resource.amount > 0
                    ):
                        self._assign_unit_target(entity, entity.source_resource.get_center(), entity.source_resource)
                    else:
                        entity.state = "IDLE"
                        entity.source_resource = None

        self._remove_dead_entities()
        self._update_entity_height_levels()
        self._update_game_over_state()
        self.magic_missiles = [missile for missile in self.magic_missiles if missile.update()]
        self.archer_shots = [shot for shot in self.archer_shots if shot.update()]
        now_ms = pygame.time.get_ticks()
        self.click_markers = [marker for marker in self.click_markers if marker.is_alive(now_ms)]

    def _update_camera(self) -> None:
        """Scroll the viewport with keyboard keys or edge scrolling."""
        if self.menu_active:
            return

        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= CAMERA_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += CAMERA_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= CAMERA_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += CAMERA_SPEED

        mouse_x, mouse_y = self.mouse_pos
        if 0 <= mouse_y < SCREEN_HEIGHT:
            if mouse_x <= EDGE_SCROLL_MARGIN:
                dx -= CAMERA_SPEED
            elif mouse_x >= SCREEN_WIDTH - EDGE_SCROLL_MARGIN:
                dx += CAMERA_SPEED
            if mouse_y <= EDGE_SCROLL_MARGIN:
                dy -= CAMERA_SPEED
            elif mouse_y >= SCREEN_HEIGHT - EDGE_SCROLL_MARGIN:
                dy += CAMERA_SPEED

        self.camera_x += dx
        self.camera_y += dy
        self._clamp_camera()

    def draw_bottom_menu(self, screen: pygame.Surface) -> None:
        """Draw UI details for the current selection.

        Args:
            screen: Pygame surface used for rendering.
        """
        menu_rect = pygame.Rect(0, SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT, SCREEN_WIDTH, BOTTOM_MENU_HEIGHT)
        pygame.draw.rect(screen, (40, 40, 40), menu_rect)
        pygame.draw.rect(screen, (200, 200, 200), menu_rect, 2)

        self.build_peasant_buttons.clear()

        if self.selected_entities:
            start_x = MINIMAP_WIDTH + MINIMAP_PADDING * 2 + 20
            start_y = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT + 15
            x_offset = 200
            y_offset = 40
            max_cols = max(1, (SCREEN_WIDTH - start_x - 20) // x_offset)

            font_small = pygame.font.SysFont(None, 24)
            for i, entity in enumerate(self.selected_entities):
                col = i % max_cols
                row = i // max_cols
                if start_y + row * y_offset + y_offset > SCREEN_HEIGHT:
                    break

                pos_x = start_x + col * x_offset
                pos_y = start_y + row * y_offset

                cls_name = type(entity).__name__
                stats_texts = [f"{cls_name}"]

                if isinstance(entity, Unit):
                    stats_texts.append(f"HP: {entity.life}/{entity.max_life}")
                    stats_texts.append(f"ATTACK: {entity.attack_damage}")
                    stats_texts.append(f"RANGE: {entity.attack_range}")
                    stats_texts.append(f"SHIELD: {entity.shield_modifier}")
                elif isinstance(entity, Building):
                    stats_texts.append(f"HP: {entity.life}/{entity.max_life}")
                    stats_texts.append(f"SHIELD: {entity.shield_modifier}")
                    if isinstance(entity, Base) and getattr(entity, "team", None) == self.current_team:
                        if self._has_reached_unit_cap(entity.team):
                            stats_texts.append("Unit cap reached")
                        else:
                            stats_texts.append("[B] Build Peasant (50 Wood)")
                elif isinstance(entity, Resource):
                    stats_texts.append(f"Amount: {entity.amount}")

                for j, stat_text in enumerate(stats_texts):
                    color = WHITE
                    if j == 0 and hasattr(entity, "team"):
                        if entity.team == TeamColor.BLUE:
                            color = (130, 130, 255)
                        elif entity.team == TeamColor.RED:
                            color = (255, 130, 130)

                    if stat_text == "[B] Build Peasant (50 Wood)":
                        mouse_pos = self.mouse_pos
                        temp_surf = font_small.render(stat_text, True, WHITE)
                        temp_rect = temp_surf.get_rect(topleft=(pos_x, pos_y + j * 16))
                        # Hover effect for the button
                        if temp_rect.collidepoint(mouse_pos):
                            color = (255, 255, 100)

                    text_surf = font_small.render(stat_text, True, color)
                    text_rect = screen.blit(text_surf, (pos_x, pos_y + j * 16))

                    if stat_text == "[B] Build Peasant (50 Wood)" and isinstance(entity, Base):
                        self.build_peasant_buttons.append((text_rect, entity))

    def draw(self, screen: pygame.Surface) -> None:
        """Draw world entities, selection state, HUD, and pause overlay.

        The provided ``screen`` is the full display surface. The world is drawn
        into a subsurface above the bottom menu; HUD, minimap, and menus are
        drawn afterward in screen coordinates.

        Args:
            screen: Pygame surface used for rendering.
        """
        world_surface = screen.subsurface(pygame.Rect(0, 0, SCREEN_WIDTH, PLAY_AREA_HEIGHT))
        camera_offset = (self.camera_x, self.camera_y)

        self.terrain.draw(world_surface, camera_offset)
        for entity in self.all_entities:
            entity.draw(world_surface, camera_offset)
        for missile in self.magic_missiles:
            missile.draw(world_surface, camera_offset)
        for shot in self.archer_shots:
            shot.draw(world_surface, camera_offset)
        for marker in self.click_markers:
            marker.draw(world_surface, camera_offset)

        if self.dragging and self.drag_start and self.drag_end:
            x1, y1 = self._world_to_screen(self.drag_start)
            x2, y2 = self._world_to_screen(self.drag_end)
            min_x = min(x1, x2)
            max_x = max(x1, x2)
            min_y = min(y1, y2)
            max_y = max(y1, y2)
            width = max_x - min_x
            height = max_y - min_y
            selection_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            selection_surface.fill((0, 255, 0, 50))
            screen.blit(selection_surface, (min_x, min_y))
            pygame.draw.rect(screen, GREEN, (min_x, min_y, width, height), 2)

        font = pygame.font.SysFont(None, 36)
        emoji_font = pygame.font.SysFont(["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", "Noto Emoji"], 20)
        team_group = self.entities.get(self.current_team)
        ui_color = BLUE if self.current_team == TeamColor.BLUE else RED

        if team_group:
            res = team_group.resources
            num_buildings = len(team_group.bases)
            num_units = (
                len(team_group.peasents) + len(team_group.knights) + len(team_group.archers) + len(team_group.mages)
            )
        else:
            res = {"wood": 0, "cristal": 0}
            num_buildings = 0
            num_units = 0

        hud_parts: list[pygame.Surface] = [
            font.render(f"Team {self.current_team.value} | ", True, ui_color),
            emoji_font.render(WOOD_ICON, True, ui_color),
            font.render(f": {res['wood']}   ", True, ui_color),
            emoji_font.render(CRISTAL_ICON, True, ui_color),
            font.render(
                f": {res['cristal']} | Buildings: {num_buildings}   Units: {num_units}/{MAX_UNITS}", True, ui_color
            ),
        ]

        if self.paused and not self.menu_active:
            pause_label = self.game_over_message or "- PAUSED -"
            pause_text = font.render(pause_label, True, WHITE)
            text_rect = pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(pause_text, text_rect)

        hud_x = 10
        hud_y = 10
        for part_surface in hud_parts:
            screen.blit(part_surface, (hud_x, hud_y))
            hud_x += part_surface.get_width()
        self.draw_bottom_menu(screen)
        self.draw_minimap(screen)

        if self.menu_active:
            self.draw_main_menu(screen)

    def draw_minimap(self, screen: pygame.Surface) -> None:
        """Draw a compact world overview and the current camera rectangle.

        The minimap uses flattened terrain rectangles rather than grouped shapes
        because it is intentionally schematic. Click/drag behavior is handled in
        ``handle_input`` via ``_center_camera_from_minimap_pos``.
        """
        rect = self._minimap_rect()
        pygame.draw.rect(screen, (23, 32, 25), rect)
        pygame.draw.rect(screen, WHITE, rect, 2)

        scale_x = rect.width / self.map_width
        scale_y = rect.height / self.map_height

        def mini_rect(world_rect: pygame.Rect) -> pygame.Rect:
            return pygame.Rect(
                rect.left + int(world_rect.left * scale_x),
                rect.top + int(world_rect.top * scale_y),
                max(1, int(world_rect.width * scale_x)),
                max(1, int(world_rect.height * scale_y)),
            )

        for region in self.terrain.water:
            pygame.draw.rect(screen, (43, 92, 119), mini_rect(region.rect))
        for region in self.terrain.high_ground:
            pygame.draw.rect(screen, (113, 132, 77), mini_rect(region.rect))
        for region in self.terrain.ramps:
            pygame.draw.rect(screen, (158, 142, 96), mini_rect(region.rect))

        for entity in self.all_entities:
            color = getattr(entity, "color", WHITE)
            if isinstance(entity, Resource):
                color = (80, 210, 120) if isinstance(entity, Wood) else (90, 220, 240)
            mini_x = rect.left + int(entity.x * scale_x)
            mini_y = rect.top + int(entity.y * scale_y)
            pygame.draw.circle(screen, color, (mini_x, mini_y), 2)

        camera_rect = pygame.Rect(
            rect.left + int(self.camera_x * scale_x),
            rect.top + int(self.camera_y * scale_y),
            max(4, int(SCREEN_WIDTH * scale_x)),
            max(4, int(PLAY_AREA_HEIGHT * scale_y)),
        )
        pygame.draw.rect(screen, WHITE, camera_rect, 1)

    def draw_main_menu(self, screen: pygame.Surface) -> None:
        """Draw the F10 pause menu."""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        menu_width = 300
        button_height = 50
        spacing = 20
        total_height = len(self.menu_options) * (button_height + spacing) - spacing
        start_x = (SCREEN_WIDTH - menu_width) // 2
        start_y = (SCREEN_HEIGHT - total_height) // 2

        font = pygame.font.SysFont(None, 40)

        for i, option in enumerate(self.menu_options):
            rect = pygame.Rect(start_x, start_y + i * (button_height + spacing), menu_width, button_height)

            # Hover effect
            mouse_pos = self.mouse_pos
            color = (80, 80, 80) if rect.collidepoint(mouse_pos) else (40, 40, 40)

            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, WHITE, rect, 2)

            text_surf = font.render(option, True, WHITE)
            text_rect = text_surf.get_rect(center=rect.center)
            screen.blit(text_surf, text_rect)

        if self.menu_status:
            status_font = pygame.font.SysFont(None, 26)
            status_surf = status_font.render(self.menu_status, True, WHITE)
            status_rect = status_surf.get_rect(center=(SCREEN_WIDTH // 2, start_y + total_height + 30))
            screen.blit(status_surf, status_rect)
