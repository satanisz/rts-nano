"""Concrete unit classes and their special combat/interaction rules.

All units inherit the movement and base combat state machine from ``Unit``.
Concrete classes mainly select definitions and provide small behavior
overrides. When adding a new unit type, register its behavior in
``entity_factory.EntityFactory`` and consider whether the map editor should expose a
placement tool.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.content import CONTENT, UnitDefinition
from rts_nano.game.constants import AttackType
from rts_nano.game.rules import apply_damage, calculate_height_range_bonus, distance_between
from rts_nano.simulation.entities.base import Building, Entity, Resource, TeamColor, Unit

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable


class Peasant(Unit):
    """Worker unit that can gather resources and deposit them at allied bases.

    Peasants enter ``GATHERING`` after reaching a ``Resource`` target and
    ``DEPOSITING`` after reaching an allied ``Building``. The manager performs
    the actual resource transfer because it owns team resource banks.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_unit("peasant"))

    def _handle_target_reached(self) -> None:
        """Transition the peasant to gathering or depositing when appropriate."""
        if self.target_entity:
            if isinstance(self.target_entity, Resource):
                self.state = "GATHERING"
            elif isinstance(self.target_entity, Building) and self.target_entity.team == self.team:
                if getattr(self.target_entity, "is_under_construction", False):
                    self.state = "BUILDING"
                    return
                if self.current_order is not None and self.current_order.kind == "repair":
                    self.state = "REPAIRING"
                    return
                self.state = "DEPOSITING"
            elif self._is_hostile_target(self.target_entity):
                self.state = "ATTACKING"
            else:
                self.state = "IDLE"
            return

        self.state = "IDLE"


class MeleeUnit(Unit):
    """Reusable behavior for units restricted to melee attacks."""

    def __init__(self, x: int, y: int, team: TeamColor, definition: UnitDefinition) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, definition)

    def _attack(self, target: Entity) -> int:
        """Perform a melee attack."""
        if self.attack_type != AttackType.MELEE:
            self.state = "IDLE"
            return 0
        return super()._attack(target)


class DeadZoneRangedUnit(Unit):
    """Reusable ranged behavior with a dead-zone and melee fallback.

    The unit switches between melee and ranged attacks based on current target
    distance. This gives it a simple micro-management profile: it wants to keep
    enemies beyond ``RANGED_MIN_ATTACK_RANGE`` to use its stronger range.
    """

    def __init__(self, x: int, y: int, team: TeamColor, definition: UnitDefinition) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, definition)

    def _get_attack_distance(self, target: Entity) -> float:
        """Pick interaction distance based on dead-zone rules."""
        dist = distance_between(self, target)
        radius_sum = self.radius + getattr(target, "radius", 0)
        ranged_min = self.ranged_min_attack_range + radius_sum
        if dist < ranged_min:
            return self.melee_attack_range + radius_sum
        range_bonus = calculate_height_range_bonus(
            self.height_level,
            getattr(target, "height_level", 0),
            AttackType.RANGED,
        )
        return self.ranged_attack_range + range_bonus + radius_sum

    def _attack(self, target: Entity) -> int:
        """Choose melee or ranged attack mode before resolving damage."""
        dist = distance_between(self, target)
        radius_sum = self.radius + getattr(target, "radius", 0)
        ranged_min = self.ranged_min_attack_range + radius_sum

        if dist < ranged_min:
            self.attack_type = AttackType.MELEE
            self.attack_range = self.melee_attack_range
        else:
            self.attack_type = AttackType.RANGED
            self.attack_range = self.ranged_attack_range

        return super()._attack(target)


class CasterUnit(Unit):
    """Base for units that use deterministic energy-powered abilities.

    Energy and cast orders arrive with the shared Mage in Sprint S6. Keeping a
    separate semantic base now prevents artillery from inheriting caster state.
    """

    def __init__(self, x: int, y: int, team: TeamColor, definition: UnitDefinition) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, definition)


class ArtilleryUnit(Unit):
    """Reusable ranged-only behavior for long-range artillery units."""

    def __init__(self, x: int, y: int, team: TeamColor, definition: UnitDefinition) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, definition)


class Knight(MeleeUnit):
    """Shared dependable melee unit available to both factions."""

    def __init__(self, x: int, y: int, team: TeamColor) -> None:
        """Initialize from the shared Knight definition."""
        super().__init__(x, y, team, CONTENT.get_unit("knight"))


class Archer(DeadZoneRangedUnit):
    """Shared ranged unit with a readable dead-zone and melee fallback."""

    def __init__(self, x: int, y: int, team: TeamColor) -> None:
        """Initialize from the shared Archer definition."""
        super().__init__(x, y, team, CONTENT.get_unit("archer"))


class Mage(CasterUnit):
    """Shared tier-two caster using a basic magic attack before doctrines."""

    def __init__(self, x: int, y: int, team: TeamColor) -> None:
        """Initialize from the shared Mage definition."""
        super().__init__(x, y, team, CONTENT.get_unit("mage"))


# --- AEGIS (Blue): precision / armored / ranged elite. Signature mechanics
# (shields, splash) are layered on in later phases; here they carry their stats
# and reuse the base melee/ranged/missile behaviors via subclassing. ---


class Marksman(DeadZoneRangedUnit):
    """AEGIS ranged core: hextech rifle with long reach and a dead-zone."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize from the Marksman content definition."""
        super().__init__(x, y, team, CONTENT.get_unit("marksman"))


class Guardian(MeleeUnit):
    """AEGIS shield tank: durable, armored frontline that protects ranged units."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize from the Guardian content definition."""
        super().__init__(x, y, team, CONTENT.get_unit("guardian"))


class Arclight(ArtilleryUnit):
    """AEGIS artillery: very long range, high single-shot damage, fragile.

    Signature mechanic: its shots splash. The post-armor damage dealt to the
    primary target is mirrored onto every enemy unit/building within
    ``SPLASH_RADIUS`` of that target (the primary is excluded; it already took
    the hit). Splash damage routes through ``apply_damage`` like any other hit,
    so enemy shields still soak it.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, CONTENT.get_unit("arclight"))
        # Latest collidable set, captured each frame so ``_attack`` can find
        # splash victims around its target without a separate entity query.
        self._splash_candidates: list[Entity] = []

    def update(
        self,
        entities: Iterable[Entity],
        can_move_to: Callable[[Unit, tuple[float, float]], bool] | None = None,
    ) -> None:
        """Capture the frame's entities for splash, then run normal unit update."""
        self._splash_candidates = list(entities)
        super().update(self._splash_candidates, can_move_to)

    def _attack(self, target: Entity) -> int:
        """Resolve the primary hit, then splash its damage onto nearby enemies."""
        damage = super()._attack(target)
        if damage > 0:
            self._apply_splash(target, damage)
        return damage

    def _apply_splash(self, primary: Entity, damage: int) -> None:
        """Deal ``damage`` to each enemy within ``SPLASH_RADIUS`` of the primary."""
        center_x, center_y = primary.get_center()
        radius_squared = self.splash_radius**2
        for entity in self._splash_candidates:
            if entity is primary or entity is self or entity.life <= 0:
                continue
            if getattr(entity, "team", None) == self.team:
                continue
            entity_x, entity_y = entity.get_center()
            if (entity_x - center_x) ** 2 + (entity_y - center_y) ** 2 <= radius_squared:
                apply_damage(entity, damage)


# --- RUST (Red): cheap / fast / expendable swarm. Poison/frenzy are layered on
# in later phases. ---


class Ripper(MeleeUnit):
    """RUST swarm melee: very fast and cheap, weak alone, terrifying in numbers.

    Frenzy: once wounded below half life it lashes out faster, so a swarm only
    gets more dangerous as it takes losses.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.RED) -> None:
        """Initialize from the Ripper content definition."""
        super().__init__(x, y, team, CONTENT.get_unit("ripper"))


class Spitter(DeadZoneRangedUnit):
    """RUST chem thrower: cheap short-range ranged poke that poisons on hit."""

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.RED) -> None:
        """Initialize from the Spitter content definition."""
        super().__init__(x, y, team, CONTENT.get_unit("spitter"))


class Brute(MeleeUnit):
    """RUST heavy melee: a slow, tanky wrecking ball whose hits poison hard.

    Frenzy: like the Ripper, it speeds up once below half life, making a wounded
    Brute a frightening clean-up threat rather than an easy finish.
    """

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.RED) -> None:
        """Initialize from the Brute content definition."""
        super().__init__(x, y, team, CONTENT.get_unit("brute"))
