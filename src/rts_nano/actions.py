"""Typed action models accepted by the public RTS Nano environment."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from rts_nano.game.assets.entities import TeamColor
    from rts_nano.game.observations import EntityId

type WorldPoint = tuple[float, float]
type ActionKind = Literal["no_op", "move", "attack", "gather", "deposit", "build", "cancel_production", "select"]


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
class BuildAction:
    """Attempt to produce a unit from a team base."""

    team: TeamColor
    base_id: EntityId | None = None
    unit_type: Literal["peasant"] = "peasant"
    frames: int = 1


@dataclass(frozen=True, slots=True)
class CancelProductionAction:
    """Cancel the active production job at a team base."""

    team: TeamColor
    base_id: EntityId | None = None
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
    | BuildAction
    | CancelProductionAction
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
