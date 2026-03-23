"""Game state coordination, input handling, and rendering."""

import math
from dataclasses import dataclass

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
    RED,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    WHITE,
    AttackType,
)


@dataclass
class MagicMissile:
    """Simple projectile effect used for mage ranged attacks."""

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

    def draw(self, screen: pygame.Surface) -> None:
        """Render a bright core with a soft glow for readability."""
        pygame.draw.circle(screen, (120, 235, 255), (int(self.x), int(self.y)), self.radius + 3)
        pygame.draw.circle(screen, CYAN, (int(self.x), int(self.y)), self.radius)
        pygame.draw.circle(screen, WHITE, (int(self.x), int(self.y)), 2)


@dataclass
class ArcherShot:
    """Simple projectile effect used for archer ranged attacks."""

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

    def draw(self, screen: pygame.Surface) -> None:
        """Render a dark arrow-like bolt with a subtle trail."""
        pygame.draw.circle(screen, (70, 70, 70), (int(self.x), int(self.y)), self.radius + 2)
        pygame.draw.circle(screen, BLACK, (int(self.x), int(self.y)), self.radius)


class EntitiesGroup:
    """Store team-owned entities and collected resources.

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
    """Store neutral resource nodes available on the map."""

    def __init__(self) -> None:
        """Initialize the object."""
        self.cristals: list[Cristal] = []
        self.woods: list[Wood] = []


class EntityFactory:
    """Create game entities from map configuration values."""

    _TEAM_ENTITY_TYPES: dict[str, type[Entity]] = {
        "peasant": Peasant,
        "knight": Knight,
        "archer": Archer,
        "mage": Mage,
        "base": Base,
    }
    _NEUTRAL_ENTITY_TYPES: dict[str, type[Entity]] = {
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
            return team_entity_type(x, y, team=team)

        neutral_entity_type = cls._NEUTRAL_ENTITY_TYPES.get(asset_type)
        if neutral_entity_type is not None:
            return neutral_entity_type(x, y)

        raise ValueError(f"Unknown asset type: {asset_type}")


class GameManager:
    """Coordinate input, simulation, selection, and drawing.

    Args:
        map_settings: Mapping of team names to entity types and spawn positions.
    """

    def __init__(self, map_settings: dict[str, dict[str, list[list[int]] | list[tuple[int, int]]]]) -> None:
        """Initialize the object."""
        self.map_settings = map_settings
        self.entities: dict[TeamColor, EntitiesGroup] = {}
        self.resources: ResourcesGroup = ResourcesGroup()
        self.selected_entities: list[Entity] = []
        self.current_team: TeamColor = TeamColor.BLUE
        self.dragging: bool = False
        self.drag_start: tuple[int, int] | None = None
        self.drag_end: tuple[int, int] | None = None
        self.paused: bool = False
        self.magic_missiles: list[MagicMissile] = []
        self.archer_shots: list[ArcherShot] = []

        self._load_map_settings()

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

    def _load_map_settings(self) -> None:
        """Instantiate entities from the loaded map configuration."""
        for category_str, assets in self.map_settings.items():
            team_color = TeamColor(category_str)
            group = EntitiesGroup(team_color)
            self.entities[team_color] = group

            for asset_type, coords in assets.items():
                normalized_coords = self._normalize_coords(coords)
                for x, y in normalized_coords:
                    entity = EntityFactory.create_entity(asset_type, x, y, team_color)
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

    def _normalize_coords(self, coords: list[list[int] | tuple[int, int]]) -> list[list[int] | tuple[int, int]]:
        """Normalize map coordinates to a list of coordinate pairs."""
        if isinstance(coords, list) and len(coords) == 2 and all(isinstance(value, (int, float)) for value in coords):
            return [coords]
        return coords

    def handle_input(self, event: pygame.event.Event) -> None:
        """Process keyboard and mouse input for team control and selection.

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
                self.paused = not self.paused

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            if event.button == 1:
                self.dragging = True
                self.drag_start = mouse_pos
                self.drag_end = mouse_pos

            elif event.button == 3:
                target_entity = None
                for entity in self.all_entities:
                    if entity.contains_point(mouse_pos):
                        target_entity = entity
                        break

                for entity in self.selected_entities:
                    if isinstance(entity, Unit):
                        entity.set_target(mouse_pos, target_entity)

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.dragging:
                self.dragging = False
                self.select_units_in_box()
                self.drag_start = None
                self.drag_end = None

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            self.drag_end = pygame.mouse.get_pos()

    def select_units_in_box(self) -> None:
        """Select units inside the drag rectangle or under the click point."""
        if not self.drag_start or not self.drag_end:
            return

        x1, y1 = self.drag_start
        x2, y2 = self.drag_end
        min_x = min(x1, x2)
        max_x = max(x1, x2)
        min_y = min(y1, y2)
        max_y = max(y1, y2)

        drag_distance = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
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
        """Advance game simulation, harvesting, and resource deposit logic."""
        if self.paused:
            return

        all_ents = self.all_entities
        for entity in all_ents:
            if getattr(entity, "life", 1) <= 0:
                continue

            if isinstance(entity, Unit):
                entity.update(all_ents)
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

                                new_resource = None
                                min_dist = HARVEST_SEARCH_RADIUS

                                resource_list = self.resources.woods if is_wood else self.resources.cristals
                                for replacement in resource_list:
                                    if replacement is not resource and replacement.amount > 0:
                                        dist = math.sqrt(
                                            (replacement.x - resource.x) ** 2 + (replacement.y - resource.y) ** 2
                                        )
                                        if dist < min_dist:
                                            min_dist = dist
                                            new_resource = replacement

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
                            if team_bases:
                                nearest_base = min(
                                    team_bases, key=lambda base: (base.x - entity.x) ** 2 + (base.y - entity.y) ** 2
                                )
                                entity.set_target(nearest_base.get_center(), nearest_base)
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
                        entity.set_target(entity.source_resource.get_center(), entity.source_resource)
                    else:
                        entity.state = "IDLE"
                        entity.source_resource = None

        self._remove_dead_entities()
        self.magic_missiles = [missile for missile in self.magic_missiles if missile.update()]
        self.archer_shots = [shot for shot in self.archer_shots if shot.update()]

    def draw_bottom_menu(self, screen: pygame.Surface) -> None:
        """Draw UI details for the current selection.

        Args:
            screen: Pygame surface used for rendering.
        """
        menu_rect = pygame.Rect(0, SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT, SCREEN_WIDTH, BOTTOM_MENU_HEIGHT)
        pygame.draw.rect(screen, (40, 40, 40), menu_rect)
        pygame.draw.rect(screen, (200, 200, 200), menu_rect, 2)

        if self.selected_entities:
            start_x = 20
            start_y = SCREEN_HEIGHT - BOTTOM_MENU_HEIGHT + 15
            x_offset = 200
            y_offset = 40
            max_cols = (SCREEN_WIDTH - 40) // x_offset

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
                elif isinstance(entity, Resource):
                    stats_texts.append(f"Amount: {entity.amount}")

                for j, stat_text in enumerate(stats_texts):
                    color = WHITE
                    if j == 0 and hasattr(entity, "team"):
                        if entity.team == TeamColor.BLUE:
                            color = (130, 130, 255)
                        elif entity.team == TeamColor.RED:
                            color = (255, 130, 130)
                    text_surf = font_small.render(stat_text, True, color)
                    screen.blit(text_surf, (pos_x, pos_y + j * 16))

    def draw(self, screen: pygame.Surface) -> None:
        """Draw world entities, selection state, HUD, and pause overlay.

        Args:
            screen: Pygame surface used for rendering.
        """
        for entity in self.all_entities:
            entity.draw(screen)
        for missile in self.magic_missiles:
            missile.draw(screen)
        for shot in self.archer_shots:
            shot.draw(screen)

        if self.dragging and self.drag_start and self.drag_end:
            x1, y1 = self.drag_start
            x2, y2 = self.drag_end
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

        text = font.render(
            f"Team {self.current_team.value} | Wood: {res['wood']}   Cristal: {res['cristal']} | "
            f"Buildings: {num_buildings}   Units: {num_units}",
            True,
            ui_color,
        )

        if self.paused:
            pause_text = font.render("- PAUSED -", True, WHITE)
            text_rect = pause_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            screen.blit(pause_text, text_rect)

        screen.blit(text, (10, 10))
        self.draw_bottom_menu(screen)
