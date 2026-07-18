"""Concrete unit classes and their special combat/interaction rules.

All units inherit the movement and base combat state machine from ``Unit``.
Concrete classes mainly provide balance constants, sprites, and small behavior
overrides. When adding a new unit type, also register it in
``manager.EntityFactory`` and consider whether the map editor should expose a
placement tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, TeamColor, Unit
from rts_nano.game.constants import FPS, AttackType
from rts_nano.game.rules import apply_damage, calculate_height_range_bonus, distance_between

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

# Every AEGIS unit shares the same shield regen profile; only the buffer size
# (``DEFAULT_SHIELD_MAX``) differs per unit. Regen is slow and only kicks in a
# few seconds after the unit was last hit, so shields reward disengaging rather
# than acting as constant bonus health in a sustained fight.
AEGIS_SHIELD_REGEN = 8  # shield points recovered per second out of combat
AEGIS_SHIELD_REGEN_DELAY = int(4 * FPS)  # frames out of combat before regen starts


class Peasant(Unit):
    """Worker unit that can gather resources and deposit them at allied bases.

    Peasants enter ``GATHERING`` after reaching a ``Resource`` target and
    ``DEPOSITING`` after reaching an allied ``Building``. The manager performs
    the actual resource transfer because it owns team resource banks.
    """

    SIZE = 30
    RADIUS = 10.0
    DEFAULT_SPEED = 2.0
    DEFAULT_MAX_CARRY = 10
    DEFAULT_MAX_LIFE = 5
    DEFAULT_ATTACK_DAMAGE = 3
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 0
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.MELEE,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        unit_name = self.__class__.__name__.lower()
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / f"{team.value.lower()}_{unit_name}.png"),
            str(BASE_DIR / "assets" / "portraits" / f"{unit_name}.png"),
        )

    def _handle_target_reached(self) -> None:
        """Transition the peasant to gathering or depositing when appropriate."""
        if self.target_entity:
            if isinstance(self.target_entity, Resource):
                self.state = "GATHERING"
            elif isinstance(self.target_entity, Building) and self.target_entity.team == self.team:
                if getattr(self.target_entity, "is_under_construction", False):
                    self.state = "BUILDING"
                    return
                self.state = "DEPOSITING"
            elif self._is_hostile_target(self.target_entity):
                self.state = "ATTACKING"
            else:
                self.state = "IDLE"
            return

        self.state = "IDLE"


class Knight(Unit):
    """Frontline melee unit."""

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 2.5
    DEFAULT_MAX_CARRY = 3
    DEFAULT_MAX_LIFE = 100
    DEFAULT_ATTACK_DAMAGE = 10
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 5
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.MELEE,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        unit_name = self.__class__.__name__.lower()
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / f"{team.value.lower()}_{unit_name}.png"),
            str(BASE_DIR / "assets" / "portraits" / f"{unit_name}.png"),
        )

    def _attack(self, target: Entity) -> int:
        """Perform a melee attack."""
        if self.attack_type != AttackType.MELEE:
            self.state = "IDLE"
            return 0
        return super()._attack(target)


class Archer(Unit):
    """Ranged unit with a dead-zone and melee fallback.

    The archer switches between melee and ranged attacks based on current target
    distance. This gives it a simple micro-management profile: it wants to keep
    enemies beyond ``RANGED_MIN_ATTACK_RANGE`` to use its stronger range.
    """

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 2.0
    DEFAULT_MAX_CARRY = 2
    DEFAULT_MAX_LIFE = 70
    DEFAULT_ATTACK_DAMAGE = 5
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 50
    DEFAULT_ATTACK_SPEED = 1
    MELEE_ATTACK_RANGE = 10
    RANGED_MIN_ATTACK_RANGE = 100
    RANGED_ATTACK_RANGE = 200
    DEFAULT_ATTACK_TYPE = (
        AttackType.MELEE,
        AttackType.RANGED,
    )
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        unit_name = self.__class__.__name__.lower()
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / f"{team.value.lower()}_{unit_name}.png"),
            str(BASE_DIR / "assets" / "portraits" / f"{unit_name}.png"),
        )

    def _get_attack_distance(self, target: Entity) -> float:
        """Pick interaction distance based on archer dead-zone rules."""
        dist = distance_between(self, target)
        radius_sum = self.radius + getattr(target, "radius", 0)
        ranged_min = self.RANGED_MIN_ATTACK_RANGE + radius_sum
        if dist < ranged_min:
            return self.MELEE_ATTACK_RANGE + radius_sum
        range_bonus = calculate_height_range_bonus(
            self.height_level,
            getattr(target, "height_level", 0),
            AttackType.RANGED,
        )
        return self.RANGED_ATTACK_RANGE + range_bonus + radius_sum

    def _attack(self, target: Entity) -> int:
        """Choose melee or ranged attack mode before resolving damage."""
        dist = distance_between(self, target)
        radius_sum = self.radius + getattr(target, "radius", 0)
        ranged_min = self.RANGED_MIN_ATTACK_RANGE + radius_sum

        if dist < ranged_min:
            self.attack_type = AttackType.MELEE
            self.attack_range = self.MELEE_ATTACK_RANGE
        else:
            self.attack_type = AttackType.RANGED
            self.attack_range = self.RANGED_ATTACK_RANGE

        return super()._attack(target)


class Mage(Unit):
    """Fragile long-range caster unit.

    Mages use ranged attacks only and emit ``MagicMissile`` VFX through the
    manager's attack-event pipeline.
    """

    SIZE = 40
    RADIUS = 13.0
    DEFAULT_SPEED = 1.5
    DEFAULT_MAX_CARRY = 1
    DEFAULT_MAX_LIFE = 30
    DEFAULT_ATTACK_DAMAGE = 5
    DEFAULT_ATTACK_MODIFIER = 0
    DEFAULT_ATTACK_RANGE = 500
    DEFAULT_ATTACK_SPEED = 1
    DEFAULT_ATTACK_TYPE = (AttackType.RANGED,)
    DEFAULT_SHIELD_MODIFIER = 0

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team, self.SIZE, self.RADIUS)
        unit_name = self.__class__.__name__.lower()
        self.load_image(
            str(BASE_DIR / "assets" / "sprites" / f"{team.value.lower()}_{unit_name}.png"),
            str(BASE_DIR / "assets" / "portraits" / f"{unit_name}.png"),
        )


# --- AEGIS (Blue): precision / armored / ranged elite. Signature mechanics
# (shields, splash) are layered on in later phases; here they carry their stats
# and reuse the base melee/ranged/missile behaviors via subclassing. ---


class Marksman(Archer):
    """AEGIS ranged core: hextech rifle with longer reach than a basic archer."""

    DEFAULT_MAX_LIFE = 70
    DEFAULT_ATTACK_DAMAGE = 9
    DEFAULT_SHIELD_MODIFIER = 1
    DEFAULT_SPEED = 2.2
    RANGED_ATTACK_RANGE = 210
    DEFAULT_SHIELD_MAX = 30
    DEFAULT_SHIELD_REGEN = AEGIS_SHIELD_REGEN
    DEFAULT_SHIELD_REGEN_DELAY = AEGIS_SHIELD_REGEN_DELAY


class Guardian(Knight):
    """AEGIS shield tank: durable, armored frontline that protects ranged units."""

    DEFAULT_MAX_LIFE = 150
    DEFAULT_ATTACK_DAMAGE = 8
    DEFAULT_SHIELD_MODIFIER = 4
    DEFAULT_SPEED = 1.9
    DEFAULT_SHIELD_MAX = 60
    DEFAULT_SHIELD_REGEN = AEGIS_SHIELD_REGEN
    DEFAULT_SHIELD_REGEN_DELAY = AEGIS_SHIELD_REGEN_DELAY


class Arclight(Mage):
    """AEGIS artillery: very long range, high single-shot damage, fragile.

    Signature mechanic: its shots splash. The post-armor damage dealt to the
    primary target is mirrored onto every enemy unit/building within
    ``SPLASH_RADIUS`` of that target (the primary is excluded; it already took
    the hit). Splash damage routes through ``apply_damage`` like any other hit,
    so enemy shields still soak it.
    """

    DEFAULT_MAX_LIFE = 40
    DEFAULT_ATTACK_DAMAGE = 16
    DEFAULT_ATTACK_RANGE = 520
    DEFAULT_ATTACK_SPEED = 1.3
    DEFAULT_SPEED = 1.4
    DEFAULT_SHIELD_MAX = 20
    DEFAULT_SHIELD_REGEN = AEGIS_SHIELD_REGEN
    DEFAULT_SHIELD_REGEN_DELAY = AEGIS_SHIELD_REGEN_DELAY
    SPLASH_RADIUS = 60

    def __init__(self, x: int, y: int, team: TeamColor = TeamColor.BLUE) -> None:
        """Initialize the object."""
        super().__init__(x, y, team)
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
        radius_squared = self.SPLASH_RADIUS**2
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


class Ripper(Knight):
    """RUST swarm melee: very fast and cheap, weak alone, terrifying in numbers.

    Frenzy: once wounded below half life it lashes out faster, so a swarm only
    gets more dangerous as it takes losses.
    """

    DEFAULT_MAX_LIFE = 45
    DEFAULT_ATTACK_DAMAGE = 6
    DEFAULT_SPEED = 3.0
    FRENZY = True


class Spitter(Archer):
    """RUST chem thrower: cheap short-range ranged poke that poisons on hit."""

    DEFAULT_MAX_LIFE = 40
    DEFAULT_ATTACK_DAMAGE = 6
    DEFAULT_SPEED = 2.4
    RANGED_ATTACK_RANGE = 130
    RANGED_MIN_ATTACK_RANGE = 60
    POISON_DAMAGE = 2
    POISON_DURATION = 90


class Brute(Knight):
    """RUST heavy melee: a slow, tanky wrecking ball whose hits poison hard.

    Frenzy: like the Ripper, it speeds up once below half life, making a wounded
    Brute a frightening clean-up threat rather than an easy finish.
    """

    DEFAULT_MAX_LIFE = 200
    DEFAULT_ATTACK_DAMAGE = 14
    DEFAULT_SHIELD_MODIFIER = 1
    DEFAULT_ATTACK_SPEED = 1.1
    DEFAULT_SPEED = 1.8
    POISON_DAMAGE = 3
    POISON_DURATION = 120
    FRENZY = True
