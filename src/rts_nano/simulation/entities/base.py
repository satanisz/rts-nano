"""Pure simulation entity types shared across units, buildings, and resources.

Entities own deterministic state and behavior only. Sprite loading, drawing,
animation direction, placeholders, and transient visual feedback belong to the
presentation layer. Cross-entity systems such as resource bank updates,
dead-list pruning, path creation, and attack-event consumption live in
``GameManager``.

All entity coordinates are world coordinates representing the center point.
No constructor performs file I/O or imports Pygame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from rts_nano.content import BuildingDefinition, ResourceDefinition, UnitDefinition
    from rts_nano.game.order import Order
    from rts_nano.game.types import ContentId, EntityId
from enum import StrEnum

from rts_nano.game.constants import (
    BLUE,
    FPS,
    GRAY,
    RED,
    AttackType,
)
from rts_nano.game.rules import (
    apply_damage,
    apply_poison,
    calculate_damage,
    calculate_height_damage_modifier,
    calculate_height_range_bonus,
    distance_between,
)


def init_shield(entity: Entity, shield_max: int, shield_regen: int, shield_regen_delay: int) -> None:
    """Attach a regenerating shield buffer to a combat entity (units and towers).

    The shield starts full. ``frames_since_damaged`` counts frames since the last
    hit so the ``EffectsSystem`` can honor the out-of-combat regen delay without
    needing a global tick. Entities with ``shield_max == 0`` are inert: combat and
    the effects tick both treat them as having no shield.
    """
    entity.shield_max = shield_max
    entity.shield = shield_max
    entity.shield_regen = shield_regen
    entity.shield_regen_delay = shield_regen_delay
    entity.frames_since_damaged = shield_regen_delay
    entity.shield_regen_accumulator = 0.0


class TeamColor(StrEnum):
    """Available ownership groups for game entities.

    The string values match top-level keys in map JSON files. Keep that
    serialization contract in mind when adding teams.
    """

    BLUE = "Blue"
    RED = "Red"
    GREY = "Grey"
    RESOURCES = "Resources"


class Entity:
    """Represent a selectable simulation object on the map.

    ``Entity`` is the common API consumed by selection, collision, targeting,
    minimap projection, and terrain-height refresh. Concrete subclasses should set
    gameplay fields such as ``life`` and ``team`` where applicable.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        color: Stable team color metadata consumed by presentation adapters.
        size: Sprite or rectangle size in pixels.
        radius: Interaction radius used for collisions and selection.
        class_name: Human-readable entity label.
    """

    definition: UnitDefinition | BuildingDefinition | ResourceDefinition
    content_id: ContentId
    spec_key: str
    visual_key: str

    # Shield buffer defaults shared by every entity. Only combat entities that
    # call ``init_shield`` (AEGIS units/towers) get a nonzero buffer; everything
    # else stays inert at 0 so combat and the effects tick can treat any target
    # uniformly without ``hasattr`` checks.
    shield_max: int = 0
    shield: int = 0
    shield_regen: int = 0
    shield_regen_delay: int = 0
    frames_since_damaged: int = 0
    shield_regen_accumulator: float = 0.0

    # RUST poison status: a poisoned target loses ``poison_tick_damage`` life on
    # the ``POISON_INTERVAL`` cadence until ``poison_remaining_frames`` runs out.
    # Inert (0) on everything until a poisoning attacker lands a hit.
    poison_tick_damage: int = 0
    poison_remaining_frames: int = 0
    poison_interval_counter: int = 0

    def __init__(
        self, x: float, y: float, color: tuple[int, int, int], size: int, radius: float, class_name: str
    ) -> None:
        """Initialize the object."""
        if type(self) is Entity:
            raise TypeError("Entity is an abstract base class and cannot be instantiated directly.")
        self.x: float = float(x)
        self.entity_id: EntityId | None = None
        self.y: float = float(y)
        self.color: tuple[int, int, int] = color
        self.size: int = size
        self.radius: float = radius
        self.life: int = 0
        self.class_name: str = class_name
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


class Resource(Entity):
    """Represent a harvestable world resource.

    Resources use ``amount`` instead of ``life`` as their depletion state. A
    peasant reaching a resource switches into ``GATHERING`` and manager-level
    harvesting decrements ``amount`` over time.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        name: Display name of the resource.
    """

    definition: ResourceDefinition

    def __init__(self, x: int, y: int, definition: ResourceDefinition) -> None:
        """Initialize the object."""
        if type(self) is Resource:
            raise TypeError("Resource is an abstract base class and cannot be instantiated directly.")
        self.definition = definition
        self.content_id = definition.id
        self.spec_key = definition.key
        self.visual_key = definition.visual_key
        super().__init__(x, y, GRAY, definition.size, definition.radius, definition.display_name)
        self.amount: int = definition.amount


class Building(Entity):
    """Represent a stationary structure owned by a team.

    Buildings are targetable combat entities and can receive deposited
    resources. The concrete ``Base`` subclass is also the current production
    structure for peasants.

    Args:
        x: Horizontal center position.
        y: Vertical center position.
        team: Owning team.
    """

    definition: BuildingDefinition

    def __init__(
        self,
        x: int,
        y: int,
        team: TeamColor,
        definition: BuildingDefinition,
    ) -> None:
        """Initialize the object."""
        if type(self) is Building:
            raise TypeError("Building is an abstract base class and cannot be instantiated directly.")
        color = Entity.get_team_color(team)
        self.definition = definition
        self.content_id = definition.id
        self.spec_key = definition.key
        self.visual_key = definition.visual_key
        super().__init__(x, y, color, definition.size, definition.radius, definition.display_name)
        self.team = team
        self.max_life = definition.max_life
        self.life = definition.max_life
        self.shield_modifier = definition.shield_modifier
        self.vision_range = definition.vision_range
        self.construction_total_frames = 0
        self.construction_remaining_frames = 0
        self.is_under_construction = False
        self.repair_credit = 0

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


class Unit(Entity):
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

    definition: UnitDefinition

    def __init__(self, x: int, y: int, team: TeamColor, definition: UnitDefinition) -> None:
        """Initialize the object."""
        if type(self) is Unit:
            raise TypeError("Unit is an abstract base class and cannot be instantiated directly.")
        color = Entity.get_team_color(team)
        self.definition = definition
        self.content_id = definition.id
        self.spec_key = definition.key
        self.visual_key = definition.visual_key
        super().__init__(x, y, color, definition.size, definition.radius, definition.display_name)
        self.team: TeamColor = team
        self.target_x: float = float(x)
        self.target_y: float = float(y)
        self.speed: float = definition.speed
        self.target_entity: Entity | None = None
        self.source_resource: Resource | None = None
        self.carry_wood: int = 0
        self.carry_gold: int = 0
        self.max_carry: int = definition.max_carry
        self.max_life: int = definition.max_life
        self.life: int = definition.max_life
        self.attack_damage: int = definition.attack_damage
        self.attack_modifier: int = definition.attack_modifier
        self.attack_range: int = definition.attack_range
        self.attack_speed: float = definition.attack_speed
        self.attack_types: tuple[AttackType, ...] = definition.attack_kinds
        self.attack_type: AttackType = self.attack_types[0]
        self.shield_modifier: int = definition.shield_modifier
        init_shield(self, definition.shield_max, definition.shield_regen, definition.shield_regen_delay)
        self.poison_damage: int = definition.poison_damage
        self.poison_duration: int = definition.poison_duration
        self.frenzy = definition.frenzy
        self.frenzy_health_fraction = definition.frenzy_health_fraction
        self.frenzy_cooldown_multiplier = definition.frenzy_cooldown_multiplier
        self.FRENZY_COOLDOWN_MULTIPLIER = definition.frenzy_cooldown_multiplier
        self.melee_attack_range = definition.melee_attack_range
        self.ranged_min_attack_range = definition.ranged_min_attack_range
        self.ranged_attack_range = definition.ranged_attack_range
        self.splash_radius = definition.splash_radius
        self.attack_cooldown: int = 0
        self.last_attack_event: tuple[tuple[float, float], tuple[float, float], AttackType, Entity] | None = None
        self.path: list[tuple[float, float]] = []
        self.attack_move_destination: tuple[float, float] | None = None
        self.patrol_points: tuple[tuple[float, float], tuple[float, float]] | None = None
        self.current_order: Order | None = None
        self.order_queue: list[Order] = []
        self.state = "IDLE"
        self.progress_anchor_x: float = float(x)
        self.progress_anchor_y: float = float(y)
        self.stuck_frames: int = 0
        self.unstuck_cooldown: int = 0
        self.path_obstacle_revision: int = 0
        self.path_unreachable: bool = False
        self.vision_range: int = definition.vision_range

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
        self.attack_move_destination = None
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

    def _attack(self, target: Entity) -> int:
        """Apply damage to a hostile target when the cooldown has elapsed.

        Returns the post-armor damage dealt to ``target`` this call (0 when no
        attack landed: out of range, on cooldown, or non-hostile). Subclasses
        with on-hit effects (e.g. Arclight splash) use the return value to mirror
        the same damage onto nearby targets.

        Damage is resolved immediately. Ranged visual projectiles are created
        later by ``GameManager`` after it consumes ``last_attack_event``. This
        separation keeps gameplay deterministic even if VFX are skipped.
        """
        if not self._is_hostile_target(target):
            self.state = "IDLE"
            return 0

        if not self._is_in_attack_range(target):
            self.state = "MOVING"
            return 0

        if self.attack_cooldown > 0:
            self.state = "ATTACKING"
            return 0

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
        apply_damage(target, damage)
        apply_poison(target, self.poison_damage, self.poison_duration)
        self.attack_cooldown = self._attack_cooldown_frames()
        self.last_attack_event = ((self.x, self.y), target.get_center(), self.attack_type, target)
        self.state = "ATTACKING"
        return damage

    def _attack_cooldown_frames(self) -> int:
        """Return frames until this unit may attack again, applying frenzy if low.

        Frenzy units (RUST Ripper/Brute) attack faster once wounded; the boost is
        evaluated here, at the moment the cooldown is set, so it tracks current
        life rather than life at the start of the fight.
        """
        frames = max(1, int(self.attack_speed * FPS))
        if self.frenzy and self.life <= self.frenzy_health_fraction * self.max_life:
            frames = max(1, int(frames * self.frenzy_cooldown_multiplier))
        return frames

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
                    self.resolve_collisions(entities, can_move_to)
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

        self.resolve_collisions(entities, can_move_to)

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

    def resolve_collisions(
        self,
        entities: Iterable[Entity],
        can_move_to: Callable[[Unit, tuple[float, float]], bool] | None = None,
    ) -> None:
        """Push the unit away from overlapping entities, respecting terrain.

        Collision response is simple pairwise separation. Resources remain
        selectable targets but do not block movement, matching terrain
        pathfinding. Workers also ignore allied unit collision while targeting a
        resource so multiple workers can gather from nearby nodes without
        constantly pushing each other off the resource.

        Each separation push is validated through ``can_move_to`` so collision
        response cannot shove a unit into water, rock, or off the map. A push
        blocked on one axis still applies on the other, which lets crowded units
        slide along an obstacle instead of tunnelling through it.

        Args:
            entities: Entities that may collide with the unit.
            can_move_to: Optional terrain/bounds validator for the pushed point.
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
                self._apply_separation(push_x, push_y, can_move_to)

    def _apply_separation(
        self,
        push_x: float,
        push_y: float,
        can_move_to: Callable[[Unit, tuple[float, float]], bool] | None,
    ) -> None:
        """Apply a separation push, falling back per-axis when terrain blocks it."""
        target = (self.x + push_x, self.y + push_y)
        if can_move_to is None or can_move_to(self, target):
            self.x, self.y = target
        elif can_move_to(self, (self.x + push_x, self.y)):
            self.x += push_x
        elif can_move_to(self, (self.x, self.y + push_y)):
            self.y += push_y
