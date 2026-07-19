"""Pure, short-lived outputs emitted by deterministic simulation ticks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rts_nano.game.types import ContentId, EntityId
    from rts_nano.simulation.entities.base import Entity


@dataclass(frozen=True, slots=True)
class AttackLanded:
    """Describe an already-resolved attack for optional presentation adapters."""

    attacker_id: EntityId
    attacker_content_id: ContentId
    source: tuple[float, float]
    target: tuple[float, float]
    target_entity: Entity
