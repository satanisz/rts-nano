"""Typed action models accepted by the public RTS Nano environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from rts_nano.game.assets.entities import TeamColor
    from rts_nano.game.observations import EntityId

type WorldPoint = tuple[float, float]
type UnitType = Literal["peasant", "knight", "archer", "mage"]
type BuildingType = Literal["barracks", "house"]
type ActionKind = Literal[
    "no_op",
    "move",
    "attack",
    "gather",
    "deposit",
    "return_cargo",
    "build",
    "construct",
    "cancel_construction",
    "cancel_production",
    "stop",
    "hold",
    "select",
]


@dataclass(frozen=True, slots=True)
class NoOpAction:
    """Advance the simulation without issuing an order."""

    frames: int = 1


@dataclass(frozen=True, slots=True)
class MoveAction:
    """Move a team's units to a world-space destination."""

    team: TeamColor
    destination: WorldPoint
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class AttackAction:
    """Order a team's units to attack an observed target entity."""

    team: TeamColor
    target_id: EntityId
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class GatherAction:
    """Order a team's peasants to gather from an observed resource entity."""

    team: TeamColor
    resource_id: EntityId
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class DepositAction:
    """Order a team's peasants to deposit resources at an observed base."""

    team: TeamColor
    base_id: EntityId | None = None
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class ReturnCargoAction:
    """Order carrying peasants to return resources to an allied base."""

    team: TeamColor
    base_id: EntityId | None = None
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class BuildAction:
    """Attempt to produce a unit from a team production building.

    ``base_id`` is kept for backward compatibility; it accepts any production
    building snapshot ID.
    """

    team: TeamColor
    base_id: EntityId | None = None
    unit_type: UnitType = "peasant"
    frames: int = 1


@dataclass(frozen=True, slots=True)
class ConstructAction:
    """Attempt to place and construct a building with a worker."""

    team: TeamColor
    position: WorldPoint
    builder_id: EntityId | None = None
    building_type: BuildingType = "barracks"
    frames: int = 1


@dataclass(frozen=True, slots=True)
class CancelConstructionAction:
    """Cancel an unfinished team building."""

    team: TeamColor
    building_id: EntityId | None = None
    frames: int = 1


@dataclass(frozen=True, slots=True)
class CancelProductionAction:
    """Cancel the active production job at a team production building."""

    team: TeamColor
    base_id: EntityId | None = None
    frames: int = 1


@dataclass(frozen=True, slots=True)
class StopAction:
    """Stop a team's units and clear their current unit orders."""

    team: TeamColor
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class HoldAction:
    """Hold a team's units in place."""

    team: TeamColor
    unit_ids: tuple[EntityId, ...] = ()
    frames: int = 1


@dataclass(frozen=True, slots=True)
class SelectAction:
    """Set the manager selection from entity snapshot IDs for parity with UI flows."""

    team: TeamColor
    entity_ids: tuple[EntityId, ...]
    frames: int = 1


type Action = (
    NoOpAction
    | MoveAction
    | AttackAction
    | GatherAction
    | DepositAction
    | ReturnCargoAction
    | BuildAction
    | ConstructAction
    | CancelConstructionAction
    | CancelProductionAction
    | StopAction
    | HoldAction
    | SelectAction
)


@dataclass(frozen=True, slots=True)
class ActionSpec:
    """Describe an action family and whether it is currently legal."""

    kind: ActionKind
    team: str | None = None
    target: str | None = None
    enabled: bool = True
    reason: str | None = None
    unit_type: str | None = None
    building_type: str | None = None
