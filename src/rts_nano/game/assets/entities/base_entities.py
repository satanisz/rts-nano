"""Base entity types shared across units, buildings, and resources.

The entity layer is intentionally lightweight and pygame-oriented. Entities know
how to draw themselves, test point selection, move/attack if they are units, and
resolve local collisions. Cross-entity systems such as resource bank updates,
dead-list pruning, path creation, and projectile spawning live in
``GameManager``.

All entity coordinates are world coordinates representing the center point.
Rendering accepts a camera offset and converts to screen coordinates at draw
time. Avoid storing screen-space positions on entities.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
from abc import ABC
from enum import StrEnum
from pathlib import Path

import pygame

from rts_nano.game.constants import (
    BLUE,
    FPS,
    GRAY,
    RED,
    WHITE,
    YELLOW,
    AttackType,
)
from rts_nano.game.rules import (
    calculate_damage,
    calculate_height_damage_modifier,
    calculate_height_range_bonus,
    distance_between,
)

BASE_DIR = Path(__file__).resolve().parent.parent


class TeamColor(StrEnum):
    """Available ownership groups for game entities.

    The string values match top-level keys in map JSON files. Keep that
    serialization contract in mind when adding teams.
    """

    BLUE = "Blue"
    RED = "Red"
    GREY = "Grey"
    RESOURCES = "Resources"


class Entity(ABC):
    # ruff: noqa: B024
    """Represent a drawable selectable object on the map.

    ``Entity`` is the common API consumed by selection, collision, targeting,
    minimap drawing, and terrain-height refresh. Concrete subclasses should set
    gameplay fields such as ``life`` and ``team`` where applicable.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        color: Display color used for primitive rendering.
        size: Sprite or rectangle size in pixels.
        radius: Interaction radius used for collisions and selection.
        class_name: Human-readable entity label.
    """

    def __init__(
        self, x: float, y: float, color: tuple[int, int, int], size: int, radius: float, class_name: str
    ) -> None:
        """Initialize the object."""
        if type(self) is Entity:
            raise TypeError("Entity is an abstract base class and cannot be instantiated directly.")
        self.x: float = float(x)
        self.y: float = float(y)
        self.color: tuple[int, int, int] = color
        self.size: int = size
        self.radius: float = radius
        self.selected: bool = False
        self.life: int = 0
        self.class_name: str = class_name
        self.image: pygame.Surface | None = None
        self.original_image: pygame.Surface | None = None
        self.avatar_image: pygame.Surface | None = None
        self.height_level: int = 0
        self.vision_range: int = 0

    @classmethod
    def get_team_color(cls, team: TeamColor) -> tuple[int, int, int]:
        """Return the RGB color associated with a team.

        Args:
            team: Team identifier.

        Returns:
            RGB color tuple for the team.

        Raises:
            ValueError: If the team is unknown.
        """
        if team == TeamColor.BLUE:
            return BLUE
        if team == TeamColor.RED:
            return RED
        if team == TeamColor.GREY or team == TeamColor.RESOURCES:
            return GRAY
        raise ValueError(f"Unknown team color: {team}")

    def load_image(self, image_path: str | Path | None, avatar_path: str | Path | None = None) -> None:
        """Load and scale an entity sprite from disk.

        Args:
            image_path: Path to the sprite file.
            avatar_path: Optional path to the portrait/avatar file.
        """
        if image_path:
            try:
                raw_image = pygame.image.load(image_path)

                if avatar_path:
                    try:
                        raw_avatar = pygame.image.load(avatar_path)
                        self.avatar_image = pygame.transform.scale(raw_avatar, (120, 120))
                    except Exception as exc:
                        logging.warning(f"Could not load avatar {avatar_path}: {exc}")
                        self.avatar_image = pygame.transform.scale(raw_image, (120, 120))
                else:
                    self.avatar_image = pygame.transform.scale(raw_image, (120, 120))

                self.image = pygame.transform.scale(raw_image, (int(self.size), int(self.size)))
                self.original_image = self.image
            except Exception as exc:
                logging.warning(f"Could not load image {image_path}: {exc}")
                self.image = None
                self.original_image = None
                self.avatar_image = None

    def draw(self, screen: pygame.Surface, offset: tuple[float, float] = (0, 0)) -> None:
        """Draw the entity, its collision radius, and selection outline.

        Args:
            screen: Pygame surface used for rendering.
            offset: Camera offset subtracted from world coordinates.
        """
        offset_x, offset_y = offset
        draw_x = self.x - offset_x
        draw_y = self.y - offset_y
        pygame.draw.circle(
            screen,
            self._get_hitbox_color(),
            (int(draw_x), int(draw_y)),
            int(self.radius + 2),
            self._get_hitbox_width(),
        )

        top_left_x = int(draw_x - self.size / 2)
        top_left_y = int(draw_y - self.size / 2)
        if self.image:
            screen.blit(self.image, (top_left_x, top_left_y))
        else:
            pygame.draw.rect(screen, self.color, (top_left_x, top_left_y, self.size, self.size))

        if self.selected:
            pygame.draw.rect(screen, WHITE, (top_left_x, top_left_y, self.size, self.size), 1)

    def _get_hitbox_width(self) -> int:
        """Return the stroke width used for the entity hitbox."""
        return 1

    def _get_hitbox_color(self) -> tuple[int, int, int]:
        """Return the color used for the entity hitbox."""
        return self.color

    def contains_point(self, pos: tuple[int, int]) -> bool:
        """Check whether a world position overlaps the entity bounds.

        Args:
            pos: World coordinates to test. Callers should convert from screen
                coordinates before using this method.

        Returns:
            True if the point lies inside the entity rectangle.
        """
        px, py = pos
        return (
            self.x - self.size / 2 <= px <= self.x + self.size / 2
            and self.y - self.size / 2 <= py <= self.y + self.size / 2
        )

    def get_center(self) -> tuple[float, float]:
        """Return the entity center coordinates."""
        return self.x, self.y


class Resource(Entity, ABC):
    """Represent a harvestable world resource.

    Resources use ``amount`` instead of ``life`` as their depletion state. A
    peasant reaching a resource switches into ``GATHERING`` and manager-level
    harvesting decrements ``amount`` over time.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        name: Display name of the resource.
    """

    SIZE = 15
    RADIUS = 5.0
    DEFAULT_AMOUNT = 100

    def __init__(self, x: int, y: int, name: str = "Resource") -> None:
        """Initialize the object."""
        if type(self) is Resource:
            raise TypeError("Resource is an abstract base class and cannot be instantiated directly.")
        super().__init__(x, y, GRAY, self.SIZE, self.RADIUS, name)
        self.amount: int = self.DEFAULT_AMOUNT


class Building(Entity, ABC):
    """Represent a stationary structure owned by a team.

    Buildings are targetable combat entities and can receive deposited
    resources. The concrete ``Base`` subclass is also the current production
    structure for peasants.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    SIZE = 80
    RADIUS = 20.0
    MAX_LIFE = 500
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        if type(self) is Building:
            raise TypeError("Building is an abstract base class and cannot be instantiated directly.")
        color = Entity.get_team_color(team)
        super().__init__(x, y, color, self.SIZE, self.RADIUS, "Building")
        self.team = team
        self.max_life = self.MAX_LIFE
        self.life = self.MAX_LIFE
        self.shield_modifier = self.DEFAULT_SHIELD_MODIFIER
        self.vision_range = 400
        self.construction_total_frames = 0
        self.construction_remaining_frames = 0
        self.is_under_construction = False

    @property
    def construction_progress(self) -> float:
        """Return construction progress in the inclusive range [0.0, 1.0]."""
        if self.construction_total_frames <= 0:
            return 1.0
        completed = self.construction_total_frames - self.construction_remaining_frames
        return min(1.0, max(0.0, completed / self.construction_total_frames))

    def start_construction(self, total_frames: int) -> None:
        """Mark the building as unfinished and ready for worker construction."""
        self.construction_total_frames = max(1, total_frames)
        self.construction_remaining_frames = self.construction_total_frames
        self.is_under_construction = True
        self.life = 1

    def advance_construction(self, frames: int = 1) -> bool:
        """Advance construction and return whether the building is complete."""
        if not self.is_under_construction:
            return True
        self.construction_remaining_frames = max(0, self.construction_remaining_frames - max(0, frames))
        self.life = max(1, int(self.max_life * self.construction_progress))
        if self.construction_remaining_frames == 0:
            self.is_under_construction = False
            self.life = self.max_life
            return True
        return False


class Unit(Entity, ABC):
    """Represent a moving controllable entity.

    Units own their movement/combat state machine. A target can be a point or an
    entity. If an entity target is hostile, the unit moves until it is in attack
    range and then applies damage on cooldown. If a target is friendly/resource,
    subclass hooks decide what state to enter after reaching interaction range.

    ``path`` is optional waypoint guidance supplied by ``GameManager``. When no
    path is present, the unit moves directly toward ``target_x/target_y``.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
        size: Sprite or rectangle size in pixels.
        radius: Interaction radius used for collisions and selection.
    """

    DEFAULT_SPEED: float = 0.0
    DEFAULT_MAX_CARRY: int = 0
    DEFAULT_MAX_LIFE: int = 0
    DEFAULT_ATTACK_DAMAGE: int = 0
    DEFAULT_ATTACK_MODIFIER: int = 0
    DEFAULT_ATTACK_RANGE: int = 0
    DEFAULT_ATTACK_SPEED: float = 0
    DEFAULT_ATTACK_TYPE: tuple[AttackType, ...] = (AttackType.NONE,)
    DEFAULT_SHIELD_MODIFIER: int = 0
    HIT_FLASH_DURATION_MS: int = 120

    def __init__(self, x: int, y: int, team: TeamColor, size: int, radius: float) -> None:
        """Initialize the object."""
        if type(self) is Unit:
            raise TypeError("Unit is an abstract base class and cannot be instantiated directly.")
        color = Entity.get_team_color(team)

        super().__init__(x, y, color, size, radius, "Unit")
        self.team: TeamColor = team
        self.default_facing: str = "right" if team == TeamColor.BLUE else "left"
        self.facing: str = self.default_facing
        self.prev_x: float = float(x)
        self.target_x: float = float(x)
        self.target_y: float = float(y)
        self.speed: float = self.DEFAULT_SPEED
        self.target_entity: Entity | None = None
        self.source_resource: Resource | None = None
        self.carry_wood: int = 0
        self.carry_cristal: int = 0
        self.max_carry: int = self.DEFAULT_MAX_CARRY
        self.max_life: int = self.DEFAULT_MAX_LIFE
        self.life: int = self.DEFAULT_MAX_LIFE
        self.attack_damage: int = self.DEFAULT_ATTACK_DAMAGE
        self.attack_modifier: int = self.DEFAULT_ATTACK_MODIFIER
        self.attack_range: int = self.DEFAULT_ATTACK_RANGE
        self.attack_speed: float = self.DEFAULT_ATTACK_SPEED
        if isinstance(self.DEFAULT_ATTACK_TYPE, tuple):
            self.attack_types: tuple[AttackType, ...] = self.DEFAULT_ATTACK_TYPE
        else:
            self.attack_types = (self.DEFAULT_ATTACK_TYPE,)
        self.attack_type: AttackType = self.attack_types[0]
        self.shield_modifier: int = self.DEFAULT_SHIELD_MODIFIER
        self.attack_cooldown: int = 0
        self.hit_flash_until_ms: int = 0
        self.last_attack_event: tuple[tuple[float, float], tuple[float, float], AttackType, Entity] | None = None
        self.path: list[tuple[float, float]] = []
        self.state = "IDLE"
        self.progress_anchor_x: float = float(x)
        self.progress_anchor_y: float = float(y)
        self.stuck_frames: int = 0
        self.unstuck_cooldown: int = 0
        self.vision_range: int = 250

    def draw(self, screen: pygame.Surface, offset: tuple[float, float] = (0, 0)) -> None:
        """Draw the unit and flip the sprite to match movement direction.

        Args:
            screen: Pygame surface used for rendering.
            offset: Camera offset subtracted from world coordinates.
        """
        dx = self.x - self.prev_x
        if dx > 0.1:
            self.facing = "right"
        elif dx < -0.1:
            self.facing = "left"

        if self.original_image is not None:
            if self.facing != self.default_facing:
                self.image = pygame.transform.flip(self.original_image, True, False)
            else:
                self.image = self.original_image

        self.prev_x = self.x

        super().draw(screen, offset)

    def _get_hitbox_width(self) -> int:
        """Return the hitbox width for units."""
        return 1

    def _get_hitbox_color(self) -> tuple[int, int, int]:
        """Return a one-shot flash color after a successful hit."""
        if self._is_hit_flash_active():
            return YELLOW
        return self.color

    def _trigger_hit_flash(self) -> None:
        """Start a short visual flash to indicate a landed hit."""
        self.hit_flash_until_ms = pygame.time.get_ticks() + self.HIT_FLASH_DURATION_MS

    def _is_hit_flash_active(self) -> bool:
        """Return whether the hit flash is currently visible."""
        return pygame.time.get_ticks() < self.hit_flash_until_ms

    def set_target(self, pos: tuple[float, float], target_entity: Entity | None = None) -> None:
        """Assign a movement or interaction target.

        The unit keeps a linked source resource for continuous harvesting when
        the target is a resource. Otherwise the stored source resource is
        cleared for manual move orders.

        Args:
            pos: Destination coordinates.
            target_entity: Optional entity to interact with at the destination.
        """
        self.target_x, self.target_y = pos
        self.target_entity = target_entity
        self.path.clear()
        self.progress_anchor_x = self.x
        self.progress_anchor_y = self.y
        self.stuck_frames = 0
        self.unstuck_cooldown = 0

        if isinstance(target_entity, Resource):
            self.source_resource = target_entity
        elif target_entity is None:
            self.source_resource = None

        self.state = "MOVING"

    def set_path(self, path: list[tuple[float, float]]) -> None:
        """Assign a path of movement waypoints.

        The final path waypoint is normally the exact requested goal. Empty path
        means direct steering is still allowed; it does not cancel the target.
        """
        self.path = path

    def _get_next_movement_target(self) -> tuple[float, float]:
        """Return the next waypoint or final target position."""
        if not self.path:
            return self._get_target_position()

        waypoint_x, waypoint_y = self.path[0]
        if ((waypoint_x - self.x) ** 2 + (waypoint_y - self.y) ** 2) ** 0.5 <= max(self.speed, 2):
            self.path.pop(0)
            if not self.path:
                return self._get_target_position()
            waypoint_x, waypoint_y = self.path[0]
        return waypoint_x, waypoint_y

    def _handle_target_reached(self) -> None:
        """Handle unit behavior after reaching its target entity or point."""
        self.state = "IDLE"

    def _is_alive_entity(self, entity: object) -> bool:
        """Return whether an entity should still be considered alive."""
        if entity is None:
            return False
        if isinstance(entity, Resource):
            return entity.amount > 0
        return getattr(entity, "life", 1) > 0

    def _is_hostile_target(self, entity: object) -> bool:
        """Return whether the target belongs to an opposing team."""
        return (
            entity is not None
            and hasattr(entity, "team")
            and entity.team != self.team
            and self._is_alive_entity(entity)
        )

    def _get_target_position(self) -> tuple[float, float]:
        """Return the current target position, following target entities."""
        if self.target_entity and self._is_alive_entity(self.target_entity):
            return self.target_entity.get_center()
        return self.target_x, self.target_y

    def _get_attack_distance(self, target: Entity) -> float:
        """Return the maximum center-to-center distance for a valid hit."""
        range_bonus = calculate_height_range_bonus(
            self.height_level,
            getattr(target, "height_level", 0),
            self.attack_type,
        )
        return self.attack_range + range_bonus + self.radius + getattr(target, "radius", 0)

    def _is_in_attack_range(self, target: Entity) -> bool:
        """Return whether the current target is inside attack range."""
        return distance_between(self, target) <= self._get_attack_distance(target)

    def _get_interaction_distance(self) -> float:
        """Return how close the unit must get to complete the current order."""
        if self.target_entity and self._is_hostile_target(self.target_entity):
            return self._get_attack_distance(self.target_entity)
        if self.target_entity:
            return self.radius + self.target_entity.radius + 2
        return self.speed

    def _attack(self, target: Entity) -> None:
        """Apply damage to a hostile target when the cooldown has elapsed.

        Damage is resolved immediately. Ranged visual projectiles are created
        later by ``GameManager`` after it consumes ``last_attack_event``. This
        separation keeps gameplay deterministic even if VFX are skipped.
        """
        if not self._is_hostile_target(target):
            self.state = "IDLE"
            return

        if not self._is_in_attack_range(target):
            self.state = "MOVING"
            return

        if self.attack_cooldown > 0:
            self.state = "ATTACKING"
            return

        height_modifier = calculate_height_damage_modifier(
            self.height_level,
            getattr(target, "height_level", 0),
            self.attack_type,
        )
        damage = calculate_damage(
            self.attack_damage,
            self.attack_modifier + height_modifier,
            getattr(target, "shield_modifier", 0),
        )
        target.life -= damage
        self.attack_cooldown = max(1, int(self.attack_speed * FPS))
        self._trigger_hit_flash()
        self.last_attack_event = ((self.x, self.y), target.get_center(), self.attack_type, target)
        self.state = "ATTACKING"

    def consume_attack_event(self) -> tuple[tuple[float, float], tuple[float, float], AttackType, Entity] | None:
        """Return and clear the latest attack event emitted by the unit.

        The manager calls this once per frame after ``update``. Add new combat
        VFX by extending the manager's attack-event handling, not by making units
        draw projectiles directly.
        """
        attack_event = self.last_attack_event
        self.last_attack_event = None
        return attack_event

    def update(
        self,
        entities: Iterable[Entity],
        can_move_to: Callable[[Unit, tuple[float, float]], bool] | None = None,
    ) -> None:
        """Advance unit movement, interaction, attacks, and collision response.

        This method is intentionally local: it can inspect nearby entities and
        call the terrain movement validator, but it does not mutate team
        resource banks or global entity lists. Manager-level systems handle
        those cross-cutting changes after each unit update.

        Args:
            entities: Entities used for movement interaction and collision
                resolution.
            can_move_to: Optional terrain movement validator.
        """
        if self.attack_cooldown > 0:
            self.attack_cooldown -= 1

        if self.target_entity and not self._is_alive_entity(self.target_entity):
            self.target_entity = None
            self.state = "IDLE"

        if self.state in {"MOVING", "ATTACKING"}:
            self.target_x, self.target_y = self._get_next_movement_target()
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            dist = (dx**2 + dy**2) ** 0.5

            is_final_entity_waypoint = bool(self.path and len(self.path) == 1 and self.target_entity)
            interaction_dist = self._get_interaction_distance() if is_final_entity_waypoint else max(self.speed, 2)
            if not self.path:
                interaction_dist = self._get_interaction_distance()

            if dist < interaction_dist:
                if self.path:
                    if not is_final_entity_waypoint:
                        self.x = self.target_x
                        self.y = self.target_y
                    self.path.pop(0)
                    if self.path:
                        self.state = "MOVING"
                    elif self.target_entity and self._is_hostile_target(self.target_entity):
                        self._attack(self.target_entity)
                    else:
                        self._handle_target_reached()
                    self.resolve_collisions(entities)
                    return
                if self.target_entity and self._is_hostile_target(self.target_entity):
                    self._attack(self.target_entity)
                else:
                    if not self.target_entity:
                        self.x = self.target_x
                        self.y = self.target_y
                    self._handle_target_reached()
            elif dist > 0:
                self.state = "MOVING"
                next_x = self.x + (dx / dist) * self.speed
                next_y = self.y + (dy / dist) * self.speed
                self._try_move_to(next_x, next_y, can_move_to)
            else:
                if self.target_entity and self._is_hostile_target(self.target_entity):
                    self._attack(self.target_entity)
                else:
                    self.x = self.target_x
                    self.y = self.target_y
                    self._handle_target_reached()

        self.resolve_collisions(entities)

    def _try_move_to(
        self,
        next_x: float,
        next_y: float,
        can_move_to: Callable[[Unit, tuple[float, float]], bool] | None,
    ) -> None:
        """Move to a valid next point, with a small axis-slide fallback."""
        if can_move_to is None or can_move_to(self, (next_x, next_y)):
            self.x = next_x
            self.y = next_y
            return

        if can_move_to(self, (next_x, self.y)):
            self.x = next_x
            return

        if can_move_to(self, (self.x, next_y)):
            self.y = next_y
            return

        self.state = "IDLE"

    def resolve_collisions(self, entities: Iterable[Entity]) -> None:
        """Push the unit away from overlapping entities.

        Collision response is simple pairwise separation. Resources remain
        selectable targets but do not block movement, matching terrain
        pathfinding. Workers also ignore allied unit collision while targeting a
        resource so multiple workers can gather from nearby nodes without
        constantly pushing each other off the resource.

        Args:
            entities: Entities that may collide with the unit.
        """
        my_cx, my_cy = self.get_center()

        for entity in entities:
            if entity is self:
                continue
            if isinstance(entity, Resource):
                continue
            if isinstance(self.target_entity, Resource) and isinstance(entity, Unit) and entity.team == self.team:
                continue

            other_cx, other_cy = entity.get_center()
            dx = my_cx - other_cx
            dy = my_cy - other_cy
            dist = (dx**2 + dy**2) ** 0.5

            min_dist = self.radius + entity.radius

            if dist < min_dist and dist > 0:
                overlap = min_dist - dist
                push_x = (dx / dist) * (overlap / 2)
                push_y = (dy / dist) * (overlap / 2)

                self.x += push_x
                self.y += push_y
