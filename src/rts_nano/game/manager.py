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

from rts_nano.game.assets.entities import Archer, Barracks, Base, Cristal, Knight, Mage, Peasant, TeamColor, Wood
from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, Unit
from rts_nano.game.constants import (
    BLACK,
    BLUE,
    BOTTOM_MENU_HEIGHT,
    CYAN,
    GREEN,
    HARVEST_SEARCH_RADIUS,
    MAX_SELECTION_SIZE,
    MAX_UNITS,
    RED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE,
    AttackType,
)
from rts_nano.game.construction import ConstructionSystem
from rts_nano.game.data import UNIT_SPECS, get_building_spec
from rts_nano.game.fog import FogOfWar
from rts_nano.game.orders import OrderSystem
from rts_nano.game.pathfinding import find_path
from rts_nano.game.production import ProductionSystem
from rts_nano.game.rules import clamp_point, distance_between_points, find_replacement_resource, nearest_entity
from rts_nano.game.terrain import TerrainMap

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

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
FORMATION_SPACING = 38
STUCK_FRAME_LIMIT = 75
STUCK_PROGRESS_DISTANCE = 6.0
UNSTUCK_COOLDOWN_FRAMES = 45


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
        self.barracks: list[Barracks] = []
        self.peasents: list[Peasant] = []
        self.knights: list[Knight] = []
        self.archers: list[Archer] = []
        self.mages: list[Mage] = []

    @property
    def all_entities(self) -> list[Entity]:
        """Return all entities owned by the team."""
        all_ents: list[Entity] = []
        all_ents.extend(self.bases)
        all_ents.extend(self.barracks)
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
        "barracks": Barracks,
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
        self.production_buttons: list[tuple[pygame.Rect, Building, str]] = []
        self.cancel_production_buttons: list[tuple[pygame.Rect, Building]] = []
        self.production = ProductionSystem(self)
        self.construction = ConstructionSystem(self)
        self.orders = OrderSystem(self)
        self.game_over_message: str | None = None
        self.menu_status: str | None = None
        self.mouse_pos: tuple[int, int] = (0, 0)
        self.camera_x: float = 0
        self.camera_y: float = 0
        self.map_width = max(self.terrain.width, SCREEN_WIDTH)
        self.map_height = max(self.terrain.height, PLAY_AREA_HEIGHT)

        self.fog = FogOfWar(self.map_width, self.map_height)

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
            for attr_name in ("peasents", "knights", "archers", "mages", "bases", "barracks"):
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

    def units_for_team(self, team: TeamColor) -> list[Unit]:
        """Return all living units owned by a team."""
        return self.orders.units_for_team(team)

    def bases_for_team(self, team: TeamColor) -> list[Base]:
        """Return all bases owned by a team."""
        return self.orders.bases_for_team(team)

    def production_buildings_for_team(self, team: TeamColor) -> list[Building]:
        """Return all production-capable buildings owned by a team."""
        return self.orders.production_buildings_for_team(team)

    def issue_move_order(
        self,
        team: TeamColor,
        destination: tuple[float, float],
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Assign a move order to team units and return the affected count."""
        return self.orders.issue_move_order(team, destination, units)

    def issue_target_order(
        self,
        team: TeamColor,
        target: Entity,
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Assign a target interaction order and return the affected count."""
        return self.orders.issue_target_order(team, target, units)

    def build_peasant(self, base: Base) -> bool:
        """Attempt to queue a Peasant at the given base."""
        return self.orders.build_peasant(base)

    def produce_unit(self, producer: Building, unit_type: str) -> bool:
        """Attempt to queue a unit at a production building."""
        return self.orders.produce_unit(producer, unit_type)

    def construct_building(self, builder: Peasant, building_type: str, position: tuple[float, float]) -> bool:
        """Attempt to place a new building and assign a worker to construct it."""
        return self.orders.construct_building(builder, building_type, position)

    def cancel_production(self, producer: Building) -> bool:
        """Attempt to cancel active production at a production building."""
        return self.orders.cancel_production(producer)

    def cancel_peasant_production(self, base: Base) -> bool:
        """Attempt to cancel active Peasant production at the given base."""
        return self.cancel_production(base)

    def select_entities_for_team(self, team: TeamColor, entities: Iterable[Entity]) -> int:
        """Select team-owned units/buildings and return the selected count."""
        return self.orders.select_entities_for_team(team, entities)

    def _count_units(self, team: TeamColor) -> int:
        """Return the number of living units owned by a team."""
        group = self.entities.get(team)
        if group is None:
            return 0
        return len(group.peasents) + len(group.knights) + len(group.archers) + len(group.mages)

    def _has_reached_unit_cap(self, team: TeamColor) -> bool:
        """Return whether a team is at the current unit cap."""
        return self._count_units(team) + self.production.queued_population_for_team(
            team
        ) >= self.population_cap_for_team(team)

    def population_cap_for_team(self, team: TeamColor) -> int:
        """Return the current population cap for a team."""
        if team == TeamColor.RESOURCES:
            return 0
        return MAX_UNITS

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
        movement_cache: dict[tuple[tuple[float, float], tuple[float, float]], bool] = {}

        def can_move_between(current: tuple[float, float], next_point: tuple[float, float]) -> bool:
            key = (current, next_point)
            if key not in movement_cache:
                movement_cache[key] = self.terrain.can_move_between(
                    current,
                    next_point,
                    radius=unit.radius,
                )
            return movement_cache[key]

        return find_path(
            unit.get_center(),
            goal,
            width=self.map_width,
            height=self.map_height,
            can_move_between=can_move_between,
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

    def _assign_group_move_order(self, units: list[Unit], destination: tuple[int, int]) -> None:
        """Assign a ground move order, spreading units across formation slots."""
        if not units:
            return
        slots = self._formation_destinations(destination, len(units))
        remaining_slots = slots.copy()
        for unit in sorted(
            units, key=lambda selected_unit: distance_between_points(selected_unit.get_center(), destination)
        ):
            slot = min(remaining_slots, key=lambda candidate: distance_between_points(unit.get_center(), candidate))
            remaining_slots.remove(slot)
            self._assign_unit_target(unit, slot)

    def _formation_destinations(self, center: tuple[int, int], count: int) -> list[tuple[int, int]]:
        """Return terrain-valid formation slots around a clicked ground point."""
        if count <= 1:
            return [center]

        columns = math.ceil(math.sqrt(count))
        rows = math.ceil(count / columns)
        offsets: list[tuple[float, float]] = []
        for row in range(rows):
            for column in range(columns):
                offset_x = (column - (columns - 1) / 2) * FORMATION_SPACING
                offset_y = (row - (rows - 1) / 2) * FORMATION_SPACING
                offsets.append((offset_x, offset_y))

        offsets.sort(key=lambda offset: offset[0] ** 2 + offset[1] ** 2)
        destinations: list[tuple[int, int]] = []
        for offset_x, offset_y in offsets[:count]:
            slot = self._clamp_to_world((center[0] + offset_x, center[1] + offset_y))
            if self.terrain.blocks_movement(slot):
                slot = center
            destinations.append(slot)
        return destinations

    def _update_unit_stuck_recovery(self, unit: Unit) -> None:
        """Recover units nudged off path by local collision resolution."""
        if unit.unstuck_cooldown > 0:
            unit.unstuck_cooldown -= 1

        if unit.state != "MOVING":
            unit.progress_anchor_x = unit.x
            unit.progress_anchor_y = unit.y
            unit.stuck_frames = 0
            return

        progress_distance = distance_between_points((unit.x, unit.y), (unit.progress_anchor_x, unit.progress_anchor_y))
        if progress_distance >= STUCK_PROGRESS_DISTANCE:
            unit.progress_anchor_x = unit.x
            unit.progress_anchor_y = unit.y
            unit.stuck_frames = 0
            return

        unit.stuck_frames += 1
        if unit.stuck_frames < STUCK_FRAME_LIMIT or unit.unstuck_cooldown > 0:
            return

        if unit.path:
            unit.path.pop(0)
        elif unit.target_entity and getattr(unit.target_entity, "life", 1) > 0:
            self._assign_unit_target(unit, unit.target_entity.get_center(), unit.target_entity)

        unit.progress_anchor_x = unit.x
        unit.progress_anchor_y = unit.y
        unit.stuck_frames = 0
        unit.unstuck_cooldown = UNSTUCK_COOLDOWN_FRAMES

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
                        case Barracks():
                            group.barracks.append(entity)
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
                for rect, producer, unit_type in self.production_buttons:
                    if rect.collidepoint(mouse_pos):
                        self.produce_unit(producer, unit_type)
                        return
                for rect, producer in self.cancel_production_buttons:
                    if rect.collidepoint(mouse_pos):
                        self.cancel_production(producer)
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

                selected_units = [entity for entity in self.selected_entities if isinstance(entity, Unit)]
                if target_entity is None:
                    self._assign_group_move_order(selected_units, order_pos)
                else:
                    for entity in selected_units:
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

    def _try_build_peasant_from_selection(self) -> None:
        """Attempt to build a peasant from the first selected base."""
        for entity in self.selected_entities:
            if isinstance(entity, Base) and entity.team == self.current_team:
                self.build_peasant(entity)
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
                    cx, cy = entity.get_center()
                    is_visible = self.fog.is_visible(cx, cy)
                    is_explored = self.fog.is_explored(cx, cy)
                    is_allied = getattr(entity, "team", None) == self.current_team
                    is_resource = isinstance(entity, Resource)

                    if not is_allied:
                        if is_resource and not (is_explored or is_visible):
                            continue
                        if not is_resource and not is_visible:
                            continue

                    entity.selected = True
                    self.selected_entities.append(entity)
                    break
        else:
            for entity in self.all_entities:
                if len(self.selected_entities) >= MAX_SELECTION_SIZE:
                    break
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

        current_team_group = self.entities.get(self.current_team)
        if current_team_group:
            visible_entities = current_team_group.all_entities
            self.fog.update(visible_entities)
        else:
            self.fog.update([])

        self._update_entity_height_levels()
        all_ents = self.all_entities
        for entity in all_ents:
            if getattr(entity, "life", 1) <= 0:
                continue

            if isinstance(entity, Unit):
                entity.update(all_ents, self._can_unit_move_to)
                self._update_unit_stuck_recovery(entity)
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

        self.construction.update()
        self.production.update()
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

        self.production_buttons.clear()
        self.cancel_production_buttons.clear()

        if not self.selected_entities:
            return

        primary_entity = self.selected_entities[0]

        minimap_end_x = MINIMAP_WIDTH + MINIMAP_PADDING * 2
        command_card_width = 180
        portrait_size = 120
        portrait_box_width = portrait_size + 20

        command_card_x = SCREEN_WIDTH - command_card_width
        portrait_x = command_card_x - portrait_box_width
        center_panel_x = minimap_end_x
        center_panel_width = portrait_x - minimap_end_x

        font_small = pygame.font.SysFont(None, 24)

        if len(self.selected_entities) > 1:
            icon_size = 40
            padding = 8
            max_cols = max(1, center_panel_width // (icon_size + padding))

            start_x = center_panel_x + padding
            start_y = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT + padding

            for i, entity in enumerate(self.selected_entities):
                col = i % max_cols
                row = i // max_cols

                pos_x = start_x + col * (icon_size + padding)
                pos_y = start_y + row * (icon_size + padding)

                if pos_y + icon_size > SCREEN_HEIGHT:
                    break

                icon_rect = pygame.Rect(pos_x, pos_y, icon_size, icon_size)

                if entity.image:
                    small_img = pygame.transform.scale(entity.image, (icon_size, icon_size))
                    screen.blit(small_img, (pos_x, pos_y))
                else:
                    pygame.draw.rect(screen, entity.color, icon_rect)

                if isinstance(entity, (Unit, Building)):
                    hp_pct = max(0, entity.life / entity.max_life)
                    hp_width = int(icon_size * hp_pct)
                    hp_rect = pygame.Rect(pos_x, pos_y + icon_size - 4, icon_size, 4)
                    pygame.draw.rect(screen, (50, 50, 50), hp_rect)
                    pygame.draw.rect(
                        screen, GREEN if hp_pct > 0.5 else RED, (pos_x, pos_y + icon_size - 4, hp_width, 4)
                    )

                pygame.draw.rect(screen, WHITE, icon_rect, 1)

        else:
            start_x = center_panel_x + 20
            start_y = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT + 15

            cls_name = type(primary_entity).__name__
            stats_texts = [f"{cls_name}"]

            if isinstance(primary_entity, Unit):
                stats_texts.append(f"HP: {primary_entity.life}/{primary_entity.max_life}")
                stats_texts.append(f"ATTACK: {primary_entity.attack_damage}")
                stats_texts.append(f"RANGE: {primary_entity.attack_range}")
                stats_texts.append(f"SHIELD: {primary_entity.shield_modifier}")
            elif isinstance(primary_entity, Building):
                stats_texts.append(f"HP: {primary_entity.life}/{primary_entity.max_life}")
                if primary_entity.is_under_construction:
                    stats_texts.append(f"Build: {primary_entity.construction_progress:.0%}")
                stats_texts.append(f"SHIELD: {primary_entity.shield_modifier}")
            elif isinstance(primary_entity, Resource):
                stats_texts.append(f"Amount: {primary_entity.amount}")

            for j, stat_text in enumerate(stats_texts):
                color = WHITE
                if j == 0 and hasattr(primary_entity, "team"):
                    if primary_entity.team == TeamColor.BLUE:
                        color = (130, 130, 255)
                    elif primary_entity.team == TeamColor.RED:
                        color = (255, 130, 130)

                text_surf = font_small.render(stat_text, True, color)
                screen.blit(text_surf, (start_x, start_y + j * 20))

        avatar_y = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT + (BOTTOM_MENU_HEIGHT - portrait_size) // 2
        frame_rect = pygame.Rect(portrait_x - 2, avatar_y - 2, portrait_size + 4, portrait_size + 4)

        if hasattr(primary_entity, "avatar_image") and primary_entity.avatar_image:
            pygame.draw.rect(screen, (80, 80, 80), frame_rect)
            pygame.draw.rect(screen, WHITE, frame_rect, 2)
            screen.blit(primary_entity.avatar_image, (portrait_x, avatar_y))
        else:
            pygame.draw.rect(screen, (30, 30, 30), frame_rect)
            pygame.draw.rect(screen, WHITE, frame_rect, 2)

        cmd_cols = 3
        cmd_rows = 3
        cmd_btn_size = 46
        cmd_padding = 6
        cmd_start_x = command_card_x + 12
        cmd_start_y = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT + 10

        font_tiny = pygame.font.SysFont(None, 16)

        commands: list[tuple[str, bool, str | None, str | None]] = []
        selected_producer: Building | None = None
        if isinstance(primary_entity, Building) and getattr(primary_entity, "team", None) == self.current_team:
            selected_producer = primary_entity
            try:
                producer_key = getattr(selected_producer, "spec_key", type(selected_producer).__name__.lower())
                building_spec = get_building_spec(producer_key)
            except ValueError:
                building_spec = None

            if building_spec is not None and building_spec.produces:
                queue = self.production.queue_for(selected_producer)
                if queue:
                    active_unit = UNIT_SPECS[queue[0].unit_type].display_name
                    commands.append((f"{active_unit} {queue[0].progress:.0%}", False, None, None))
                    commands.append(("Cancel", True, "cancel", None))

                for unit_type in building_spec.produces:
                    can_build, reason = self.production.can_enqueue_unit(selected_producer, unit_type)
                    unit_name = UNIT_SPECS[unit_type].display_name
                    if can_build:
                        commands.append((f"Train {unit_name}", True, "produce", unit_type))
                    elif reason == "population_cap":
                        commands.append(("Cap Reached", False, None, None))
                    elif reason == "insufficient_resources":
                        commands.append((f"Need {unit_name}", False, None, None))
                    else:
                        commands.append(("Unavailable", False, None, None))

        for i in range(cmd_cols * cmd_rows):
            col = i % cmd_cols
            row = i // cmd_cols
            pos_x = cmd_start_x + col * (cmd_btn_size + cmd_padding)
            pos_y = cmd_start_y + row * (cmd_btn_size + cmd_padding)

            btn_rect = pygame.Rect(pos_x, pos_y, cmd_btn_size, cmd_btn_size)

            if i < len(commands):
                cmd_name, cmd_active, cmd_action, cmd_unit_type = commands[i]

                mouse_pos = self.mouse_pos
                is_hovered = btn_rect.collidepoint(mouse_pos)
                bg_color = (60, 60, 60)
                if is_hovered and cmd_active:
                    bg_color = (100, 100, 60)

                pygame.draw.rect(screen, bg_color, btn_rect)
                pygame.draw.rect(screen, WHITE, btn_rect, 1)

                words = cmd_name.split()
                for w_i, word in enumerate(words):
                    text_surf = font_tiny.render(word, True, WHITE)
                    text_rect = text_surf.get_rect(center=(pos_x + cmd_btn_size // 2, pos_y + 16 + w_i * 14))
                    screen.blit(text_surf, text_rect)

                if cmd_active and cmd_action == "produce" and selected_producer is not None and cmd_unit_type:
                    self.production_buttons.append((btn_rect, selected_producer, cmd_unit_type))
                elif cmd_active and cmd_action == "cancel" and selected_producer is not None:
                    self.cancel_production_buttons.append((btn_rect, selected_producer))

            else:
                pygame.draw.rect(screen, (30, 30, 30), btn_rect)
                pygame.draw.rect(screen, (50, 50, 50), btn_rect, 1)

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
            cx, cy = entity.get_center()
            is_visible = self.fog.is_visible(cx, cy)
            is_explored = self.fog.is_explored(cx, cy)

            is_allied = getattr(entity, "team", None) == self.current_team
            is_resource = isinstance(entity, Resource)

            if is_allied:
                entity.draw(world_surface, camera_offset)
            elif is_resource:
                if is_explored or is_visible:
                    entity.draw(world_surface, camera_offset)
            else:
                if is_visible:
                    entity.draw(world_surface, camera_offset)

        for missile in self.magic_missiles:
            if self.fog.is_visible(missile.x, missile.y):
                missile.draw(world_surface, camera_offset)
        for shot in self.archer_shots:
            if self.fog.is_visible(shot.x, shot.y):
                shot.draw(world_surface, camera_offset)
        for marker in self.click_markers:
            marker.draw(world_surface, camera_offset)

        from rts_nano.game.constants import FOG_CELL_SIZE

        fog_surf = pygame.Surface((SCREEN_WIDTH, PLAY_AREA_HEIGHT), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 255))

        start_col = max(0, int(self.camera_x // FOG_CELL_SIZE))
        end_col = min(self.fog.cols - 1, int((self.camera_x + SCREEN_WIDTH) // FOG_CELL_SIZE))
        start_row = max(0, int(self.camera_y // FOG_CELL_SIZE))
        end_row = min(self.fog.rows - 1, int((self.camera_y + PLAY_AREA_HEIGHT) // FOG_CELL_SIZE))

        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                state = self.fog.grid[row][col]
                if state > 0:
                    rect_x = int(col * FOG_CELL_SIZE - self.camera_x)
                    rect_y = int(row * FOG_CELL_SIZE - self.camera_y)
                    # Expand by 1 pixel to prevent visual seams between grid cells
                    rect = pygame.Rect(rect_x, rect_y, FOG_CELL_SIZE + 1, FOG_CELL_SIZE + 1)
                    if state == FogOfWar.VISIBLE:
                        fog_surf.fill((0, 0, 0, 0), rect)
                    else:
                        fog_surf.fill((0, 0, 0, 150), rect)

        world_surface.blit(fog_surf, (0, 0))

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
            num_buildings = len(team_group.bases) + len(team_group.barracks)
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

        from rts_nano.game.constants import FOG_CELL_SIZE

        fog_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 255))

        for row in range(self.fog.rows):
            for col in range(self.fog.cols):
                state = self.fog.grid[row][col]
                if state > 0:
                    cell_rect = pygame.Rect(
                        int(col * FOG_CELL_SIZE * scale_x),
                        int(row * FOG_CELL_SIZE * scale_y),
                        max(1, int(FOG_CELL_SIZE * scale_x)) + 1,
                        max(1, int(FOG_CELL_SIZE * scale_y)) + 1,
                    )
                    if state == FogOfWar.VISIBLE:
                        fog_surf.fill((0, 0, 0, 0), cell_rect)
                    else:
                        fog_surf.fill((0, 0, 0, 150), cell_rect)
        screen.blit(fog_surf, (rect.left, rect.top))

        for entity in self.all_entities:
            cx, cy = entity.get_center()
            is_visible = self.fog.is_visible(cx, cy)
            is_explored = self.fog.is_explored(cx, cy)
            is_allied = getattr(entity, "team", None) == self.current_team
            is_resource = isinstance(entity, Resource)

            should_draw = False
            if is_allied:
                should_draw = True
            elif is_resource:
                should_draw = is_explored or is_visible
            else:
                should_draw = is_visible

            if should_draw:
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
