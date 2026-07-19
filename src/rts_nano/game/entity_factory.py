"""Single behavior-class factory for every registered content ID."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from rts_nano.content import CONTENT
from rts_nano.simulation.entities import (
    Arclight,
    Arsenal,
    Base,
    Bastion,
    Brute,
    ChemVat,
    Gold,
    Guardian,
    House,
    Marksman,
    Peasant,
    Pit,
    Ripper,
    Spiker,
    Spire,
    Spitter,
    TeamColor,
    Wood,
)

if TYPE_CHECKING:
    from rts_nano.simulation.entities.base import Entity


class EntityFactory:
    """Map canonical content IDs to their current behavior implementations."""

    _ENTITY_TYPES: ClassVar[dict[str, type]] = {
        "peasant": Peasant,
        "base": Base,
        "house": House,
        "marksman": Marksman,
        "guardian": Guardian,
        "arclight": Arclight,
        "arsenal": Arsenal,
        "spire": Spire,
        "bastion": Bastion,
        "ripper": Ripper,
        "spitter": Spitter,
        "brute": Brute,
        "pit": Pit,
        "chem_vat": ChemVat,
        "spiker": Spiker,
        "wood": Wood,
        "gold": Gold,
    }

    @classmethod
    def create(cls, content_id: str, x: int, y: int, team: TeamColor) -> Entity:
        """Create content through its one registered behavior class."""
        try:
            entity_type = cls._ENTITY_TYPES[content_id]
        except KeyError as exc:
            raise ValueError(f"Unknown content id: {content_id}") from exc
        if content_id in {"wood", "gold"}:
            return entity_type(x, y)
        return entity_type(x, y, team)

    @classmethod
    def validate(cls) -> None:
        """Reject missing or stale behavior mappings at startup."""
        expected = set(CONTENT.units) | set(CONTENT.buildings) | set(CONTENT.resources)
        actual = set(cls._ENTITY_TYPES)
        if actual != expected:
            raise RuntimeError(
                f"Entity factory mismatch: missing={sorted(expected - actual)}, stale={sorted(actual - expected)}"
            )


EntityFactory.validate()
