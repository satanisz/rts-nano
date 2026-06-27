"""Game state coordination and simulation tick.

``GameManager`` is the central runtime object for the playable game. It owns the
loaded map, all entities, camera state, selected units, transient VFX, resource
collection, combat projectiles, and the menu/selection state. Rendering lives in
``GameRenderer``, event/input handling in ``InputController``, and the command
panel layout in ``CommandPanel``; ``main.py`` wires those adapters to the manager.

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

from rts_nano.game.assets.entities import (
    Archer,
    Barracks,
    Base,
    Gold,
    House,
    Knight,
    Mage,
    MageTower,
    Peasant,
    TeamColor,
    Tower,
    Wood,
)
from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, Unit
from rts_nano.game.combat import CombatSystem
from rts_nano.game.constants import (
    BLACK,
    BOTTOM_MENU_HEIGHT,
    CYAN,
    MAX_SELECTION_SIZE,
    MINIMAP_HEIGHT,
    MINIMAP_PADDING,
    MINIMAP_WIDTH,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE,
    AttackType,
)
from rts_nano.game.construction import ConstructionSystem
from rts_nano.game.data import get_building_spec
from rts_nano.game.fog import FogOfWar
from rts_nano.game.gather import GatherSystem
from rts_nano.game.movement import MovementSystem
from rts_nano.game.orders import OrderSystem
from rts_nano.game.production import ProductionSystem
from rts_nano.game.rules import distance_between_points
from rts_nano.game.state import EntitiesGroup, GameState, ResourcesGroup
from rts_nano.game.terrain import TerrainMap
from rts_nano.game.ui.command_panel import CommandPanel
from rts_nano.game.victory import VictorySystem

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from rts_nano.map_schema import MapSettings

FULLSCREEN_TOGGLE_EVENT = pygame.USEREVENT + 1
PLAY_AREA_HEIGHT = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT
CAMERA_SPEED = 12
EDGE_SCROLL_MARGIN = 24
DOUBLE_CLICK_MS = 350


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


class EntityFactory:
    """Create game entities from map configuration values.

    The factory is the only place that maps serialized asset names such as
    ``"peasant"`` or ``"gold"`` to concrete classes. Add new JSON entity
    types here before expecting maps or the editor to spawn them in-game.
    """

    _TEAM_ENTITY_TYPES: dict[str, Callable[[int, int, TeamColor], Entity]] = {
        "peasant": Peasant,
        "knight": Knight,
        "archer": Archer,
        "mage": Mage,
        "base": Base,
        "barracks": Barracks,
        "house": House,
        "mage_tower": MageTower,
        "tower": Tower,
    }
    _NEUTRAL_ENTITY_TYPES: dict[str, Callable[[int, int], Entity]] = {
        "wood": Wood,
        "gold": Gold,
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
        terrain = TerrainMap(map_settings.get("Terrain"))
        map_width = max(terrain.width, SCREEN_WIDTH)
        map_height = max(terrain.height, PLAY_AREA_HEIGHT)
        self.state = GameState(
            terrain=terrain,
            fog=FogOfWar(map_width, map_height),
            map_width=map_width,
            map_height=map_height,
        )
        self.control_groups: dict[int, list[Unit]] = {}
        self.dragging: bool = False
        self.minimap_dragging: bool = False
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
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
        self.command_panel = CommandPanel()
        self.pending_construction_type: str | None = None
        self.pending_construction_builder: Peasant | None = None
        self.pending_unit_command: str | None = None
        self.movement = MovementSystem(self.state)
        self.production = ProductionSystem(self.state)
        self.combat = CombatSystem(self.state)
        self.victory = VictorySystem(self.state)
        self.gather = GatherSystem(self.state, self.movement)
        self.construction = ConstructionSystem(self.state, self.movement)
        self.orders = OrderSystem(self.state, self.movement, self.production, self.construction)
        self.menu_status: str | None = None
        self.mouse_pos: tuple[int, int] = (0, 0)
        self.camera_x: float = 0
        self.camera_y: float = 0

        self._load_map_settings()
        self._update_entity_height_levels()
        self.set_viewport_size(SCREEN_WIDTH, SCREEN_HEIGHT)

    # --- GameState-backed data (single source of truth lives in self.state) ---

    @property
    def entities(self) -> dict[TeamColor, EntitiesGroup]:
        """Team entity rosters (backed by ``GameState``)."""
        return self.state.entities

    @property
    def resources(self) -> ResourcesGroup:
        """Neutral resource nodes (backed by ``GameState``)."""
        return self.state.resources

    @property
    def fog(self) -> FogOfWar:
        """Fog-of-war grid (backed by ``GameState``)."""
        return self.state.fog

    @property
    def terrain(self) -> TerrainMap:
        """Terrain map (backed by ``GameState``)."""
        return self.state.terrain

    @property
    def map_width(self) -> int:
        """World width in pixels (backed by ``GameState``)."""
        return self.state.map_width

    @map_width.setter
    def map_width(self, value: int) -> None:
        self.state.map_width = value

    @property
    def map_height(self) -> int:
        """World height in pixels (backed by ``GameState``)."""
        return self.state.map_height

    @map_height.setter
    def map_height(self, value: int) -> None:
        self.state.map_height = value

    @property
    def current_team(self) -> TeamColor:
        """Team currently controlled/viewed (backed by ``GameState``)."""
        return self.state.current_team

    @current_team.setter
    def current_team(self, value: TeamColor) -> None:
        self.state.current_team = value

    @property
    def selected_entities(self) -> list[Entity]:
        """Currently selected entities (backed by ``GameState``)."""
        return self.state.selected_entities

    @selected_entities.setter
    def selected_entities(self, value: list[Entity]) -> None:
        self.state.selected_entities = value

    @property
    def game_over_message(self) -> str | None:
        """Terminal result label, or None while playing (backed by ``GameState``)."""
        return self.state.game_over_message

    @game_over_message.setter
    def game_over_message(self, value: str | None) -> None:
        self.state.game_over_message = value

    @property
    def paused(self) -> bool:
        """Whether the simulation tick is frozen (backed by ``GameState``)."""
        return self.state.paused

    @paused.setter
    def paused(self, value: bool) -> None:
        self.state.paused = value

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

    @property
    def screen_width(self) -> int:
        """Current viewport width (dynamic with the display surface)."""
        return SCREEN_WIDTH

    @property
    def screen_height(self) -> int:
        """Current viewport height (dynamic with the display surface)."""
        return SCREEN_HEIGHT

    @property
    def play_area_height(self) -> int:
        """Current playable area height above the bottom menu."""
        return PLAY_AREA_HEIGHT

    def _remove_dead_entities(self) -> None:
        """Remove defeated units and buildings from the game state."""
        removed_entities: set[int] = set()

        for group in self.entities.values():
            for attr_name in (
                "peasents",
                "knights",
                "archers",
                "mages",
                "bases",
                "barracks",
                "houses",
                "mage_towers",
                "towers",
            ):
                entities = getattr(group, attr_name)
                alive_entities = [entity for entity in entities if entity.life > 0]
                removed_entities.update(id(entity) for entity in entities if entity.life <= 0)
                setattr(group, attr_name, alive_entities)

        if removed_entities:
            self.selected_entities = [entity for entity in self.selected_entities if id(entity) not in removed_entities]

    @property
    def all_entities(self) -> list[Entity]:
        """Return all active entities, including units, buildings, and resources."""
        return self.state.all_entities

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

    def issue_attack_move_order(
        self,
        team: TeamColor,
        destination: tuple[float, float],
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Assign an attack-move order to team units and return the affected count."""
        return self.orders.issue_attack_move_order(team, destination, units)

    def issue_patrol_order(
        self,
        team: TeamColor,
        destination: tuple[float, float],
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Assign a patrol order between current position and a destination."""
        return self.orders.issue_patrol_order(team, destination, units)

    def issue_target_order(
        self,
        team: TeamColor,
        target: Entity,
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Assign a target interaction order and return the affected count."""
        return self.orders.issue_target_order(team, target, units)

    def issue_gather_order(
        self,
        team: TeamColor,
        resource: Resource,
        units: Iterable[Unit] | None = None,
    ) -> int:
        """Order team peasants to gather from a resource node."""
        return self.orders.issue_gather_order(team, resource, units)

    def issue_stop_order(self, team: TeamColor, units: Iterable[Unit] | None = None) -> int:
        """Stop team units and clear their active targets."""
        return self.orders.issue_stop_order(team, units)

    def issue_hold_order(self, team: TeamColor, units: Iterable[Unit] | None = None) -> int:
        """Hold team units in place and clear their active targets."""
        return self.orders.issue_hold_order(team, units)

    def issue_return_cargo_order(
        self,
        team: TeamColor,
        units: Iterable[Unit] | None = None,
        base: Base | None = None,
    ) -> int:
        """Order carrying peasants to return resources to an allied base."""
        return self.orders.issue_return_cargo_order(team, units, base)

    def build_peasant(self, base: Base) -> bool:
        """Attempt to queue a Peasant at the given base."""
        return self.orders.build_peasant(base)

    def produce_unit(self, producer: Building, unit_type: str) -> bool:
        """Attempt to queue a unit at a production building."""
        return self.orders.produce_unit(producer, unit_type)

    def construct_building(self, builder: Peasant, building_type: str, position: tuple[float, float]) -> bool:
        """Attempt to place a new building and assign a worker to construct it."""
        return self.orders.construct_building(builder, building_type, position)

    def cancel_construction(self, building: Building) -> bool:
        """Attempt to cancel an unfinished building."""
        return self.orders.cancel_construction(building)

    def begin_construction_placement(self, building_type: str) -> bool:
        """Enter placement mode for a selected peasant construction command."""
        builder = self._selected_construction_builder()
        if builder is None:
            self.menu_status = "Select a peasant"
            return False

        can_construct, reason = self.construction.can_team_construct(builder.team, building_type)
        if not can_construct:
            self.menu_status = f"Cannot build: {reason}"
            return False

        self.cancel_pending_unit_command()
        self.pending_construction_type = building_type
        self.pending_construction_builder = builder
        self.menu_status = f"Place {get_building_spec(building_type).display_name}"
        return True

    def cancel_pending_construction_placement(self) -> None:
        """Leave placement mode without issuing a build order."""
        self.pending_construction_type = None
        self.pending_construction_builder = None

    def begin_attack_move_targeting(self) -> bool:
        """Enter a one-click targeting mode for the attack-move command."""
        selected_units = [entity for entity in self.selected_entities if isinstance(entity, Unit)]
        if not selected_units:
            self.menu_status = "Select units"
            return False
        self.cancel_pending_construction_placement()
        self.pending_unit_command = "attack_move"
        self.menu_status = "Choose attack-move target"
        return True

    def begin_patrol_targeting(self) -> bool:
        """Enter a one-click targeting mode for the patrol command."""
        selected_units = [entity for entity in self.selected_entities if isinstance(entity, Unit)]
        if not selected_units:
            self.menu_status = "Select units"
            return False
        self.cancel_pending_construction_placement()
        self.pending_unit_command = "patrol"
        self.menu_status = "Choose patrol point"
        return True

    def begin_gather_targeting(self) -> bool:
        """Enter a one-click targeting mode for gathering resources."""
        selected_peasants = [entity for entity in self.selected_entities if isinstance(entity, Peasant)]
        if not selected_peasants:
            self.menu_status = "Select peasants"
            return False
        self.cancel_pending_construction_placement()
        self.pending_unit_command = "gather"
        self.menu_status = "Choose resource"
        return True

    def cancel_pending_unit_command(self) -> None:
        """Leave pending selected-unit command mode."""
        self.pending_unit_command = None
        if self.menu_status in {"Choose attack-move target", "Choose resource", "Choose patrol point"}:
            self.menu_status = None

    def place_pending_construction(self, position: tuple[float, float]) -> bool:
        """Place the active construction command at a world position."""
        building_type = self.pending_construction_type
        builder = self._pending_construction_builder()
        if building_type is None or builder is None:
            self.cancel_pending_construction_placement()
            return False

        can_start, reason = self.construction.can_start_construction(builder, building_type, position)
        if not can_start:
            self.menu_status = f"Cannot place: {reason}"
            return False

        if not self.construct_building(builder, building_type, position):
            self.menu_status = "Cannot place"
            return False

        self.menu_status = None
        self.cancel_pending_construction_placement()
        return True

    def cancel_production(self, producer: Building) -> bool:
        """Attempt to cancel active production at a production building."""
        return self.orders.cancel_production(producer)

    def cancel_peasant_production(self, base: Base) -> bool:
        """Attempt to cancel active Peasant production at the given base."""
        return self.cancel_production(base)

    def select_entities_for_team(self, team: TeamColor, entities: Iterable[Entity]) -> int:
        """Select team-owned units/buildings and return the selected count."""
        return self.orders.select_entities_for_team(team, entities)

    def assign_control_group(self, group_id: int) -> int:
        """Store the current team's selected units under a control-group number."""
        units = [
            entity
            for entity in self.selected_entities
            if isinstance(entity, Unit) and entity.team == self.current_team and entity.life > 0
        ]
        self.control_groups[group_id] = units
        return len(units)

    def recall_control_group(self, group_id: int) -> int:
        """Reselect the living members of a previously stored control group."""
        members = [unit for unit in self.control_groups.get(group_id, []) if unit.life > 0]
        return self.orders.select_entities_for_team(self.current_team, members)

    def select_units_like(self, reference: Unit) -> int:
        """Select every current-team unit sharing the reference unit's type."""
        if reference.team != self.current_team:
            return 0
        same_type = [unit for unit in self.orders.units_for_team(self.current_team) if type(unit) is type(reference)]
        return self.orders.select_entities_for_team(self.current_team, same_type)

    def _handle_unit_command_button(self, command: str) -> None:
        """Apply a selected-unit command from the bottom command panel."""
        selected_units = [entity for entity in self.selected_entities if isinstance(entity, Unit)]
        if command == "stop":
            self.issue_stop_order(self.current_team, selected_units)
        elif command == "hold":
            self.issue_hold_order(self.current_team, selected_units)
        elif command == "return_cargo":
            self.issue_return_cargo_order(self.current_team, selected_units)
        elif command == "attack_move":
            self.begin_attack_move_targeting()
        elif command == "patrol":
            self.begin_patrol_targeting()
        elif command == "gather":
            self.begin_gather_targeting()

    def _count_units(self, team: TeamColor) -> int:
        """Return the number of living units owned by a team (delegates to state)."""
        return self.state.count_units(team)

    def _has_reached_unit_cap(self, team: TeamColor) -> bool:
        """Return whether a team is at the current unit cap."""
        return self._count_units(team) + self.production.queued_population_for_team(
            team
        ) >= self.population_cap_for_team(team)

    def population_cap_for_team(self, team: TeamColor) -> int:
        """Return the current population cap for a team (delegates to state)."""
        return self.state.population_cap_for_team(team)

    def _clamp_unit_to_world(self, unit: Unit) -> None:
        """Keep a unit's body inside the map after movement and collision pushes.

        Collision separation and edge steering can otherwise drift a unit's
        center past the map border. Clamping by the unit radius keeps the whole
        body on-map without affecting units away from the edges.
        """
        radius = unit.radius
        unit.x = min(max(unit.x, radius), self.map_width - radius)
        unit.y = min(max(unit.y, radius), self.map_height - radius)

    def _clamp_to_world(self, pos: tuple[float, float]) -> tuple[int, int]:
        """Clamp a world-space point to full map bounds (delegates to state)."""
        return self.state.clamp_to_world(pos)

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

    def _update_entity_height_levels(self) -> None:
        """Refresh height levels for every entity. Used once after map load."""
        for entity in self.all_entities:
            entity.height_level = self.terrain.height_at(entity.get_center())

    def _update_mobile_height_levels(self) -> None:
        """Refresh height levels for units and buildings each tick.

        Neutral resources never move and terrain is static, so resource height is
        computed once after load. Only team entities (movable units, plus
        buildings that can be constructed mid-game) need a per-tick refresh, which
        avoids re-querying terrain for every resource node every frame.
        """
        for group in self.entities.values():
            for entity in group.all_entities:
                entity.height_level = self.terrain.height_at(entity.get_center())

    def _selected_construction_builder(self) -> Peasant | None:
        return next(
            (
                entity
                for entity in self.selected_entities
                if isinstance(entity, Peasant) and entity.team == self.current_team and entity.life > 0
            ),
            None,
        )

    def _pending_construction_builder(self) -> Peasant | None:
        builder = self.pending_construction_builder
        if builder is not None and builder.team == self.current_team and builder.life > 0:
            return builder
        return self._selected_construction_builder()

    def _assign_unit_target(
        self,
        unit: Unit,
        destination: tuple[float, float],
        target_entity: Entity | None = None,
    ) -> None:
        """Assign a unit movement target and path (delegates to MovementSystem)."""
        self.movement.assign_unit_target(unit, destination, target_entity)

    def _assign_group_move_order(self, units: list[Unit], destination: tuple[int, int]) -> None:
        """Assign a group move order (delegates to MovementSystem)."""
        self.movement.assign_group_move_order(units, destination)

    def _formation_destinations(self, center: tuple[int, int], count: int) -> list[tuple[int, int]]:
        """Return formation slots around a point (delegates to MovementSystem)."""
        return self.movement.formation_destinations(center, count)

    def _unit_at_world_pos(self, position: tuple[float, float]) -> Unit | None:
        """Return the topmost unit under a world position."""
        point = (int(position[0]), int(position[1]))
        for entity in reversed(self.all_entities):
            if isinstance(entity, Unit) and entity.contains_point(point):
                return entity
        return None

    def _resource_at_position(self, position: tuple[float, float]) -> Resource | None:
        """Return the topmost resource under a world position."""
        for entity in reversed(self.all_entities):
            if isinstance(entity, Resource) and entity.contains_point((int(position[0]), int(position[1]))):
                return entity
        return None

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
                        case House():
                            group.houses.append(entity)
                        case MageTower():
                            group.mage_towers.append(entity)
                        case Tower():
                            group.towers.append(entity)
                        case Wood():
                            self.resources.woods.append(entity)
                        case Gold():
                            self.resources.golds.append(entity)

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

    def _set_menu_option(self, prefix: str, value: str) -> None:
        """Replace the first menu option that starts with prefix."""
        for index, option in enumerate(self.menu_options):
            if option.startswith(prefix):
                self.menu_options[index] = value
                return

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
        """Advance unit simulation, harvesting, combat VFX, production, and victory.

        Returns early when paused, freezing unit movement, harvesting, combat,
        projectiles, and click-marker cleanup. Camera scrolling lives in the
        ``InputController`` so it can still pan while the simulation is paused.
        """
        if self.paused:
            return

        current_team_group = self.entities.get(self.current_team)
        if current_team_group:
            visible_entities = current_team_group.all_entities
            self.fog.update(visible_entities)
        else:
            self.fog.update([])

        self._update_mobile_height_levels()
        all_ents = self.all_entities
        collidable_entities = [entity for entity in all_ents if isinstance(entity, (Unit, Building))]
        for entity in all_ents:
            if getattr(entity, "life", 1) <= 0:
                continue

            if isinstance(entity, Unit):
                self.movement.update_attack_move_target(entity, all_ents)
                entity.update(collidable_entities, self.movement.can_unit_move_to)
                self._clamp_unit_to_world(entity)
                self.movement.update_unit_stuck_recovery(entity)
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
                self.movement.resume_or_finish_attack_move(entity)
                self.movement.update_patrol(entity)

            if isinstance(entity, Peasant):
                self.gather.update_peasant(entity, all_ents)

        self.construction.update()
        self.production.update()
        for source_pos, target_pos, target in self.combat.update():
            self.archer_shots.append(
                ArcherShot(source_pos[0], source_pos[1], target_pos[0], target_pos[1], target_entity=target)
            )
        self._remove_dead_entities()
        self.victory.update()
        self.magic_missiles = [missile for missile in self.magic_missiles if missile.update()]
        self.archer_shots = [shot for shot in self.archer_shots if shot.update()]
        now_ms = pygame.time.get_ticks()
        self.click_markers = [marker for marker in self.click_markers if marker.is_alive(now_ms)]
