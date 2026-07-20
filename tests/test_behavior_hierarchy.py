"""Semantic combat behavior bases stay separate from concrete content."""

from __future__ import annotations

import rts_nano.simulation.entities as entity_exports
from rts_nano.simulation.entities import (
    Archer,
    Arclight,
    ArtilleryUnit,
    Brute,
    CasterUnit,
    DeadZoneRangedUnit,
    Guardian,
    Knight,
    Mage,
    Marksman,
    MeleeUnit,
    Ripper,
    Spitter,
)
from rts_nano.simulation.entities.base import Unit


def test_faction_units_inherit_semantic_behavior_bases() -> None:
    """Concrete content shares mechanics without inheriting other content."""
    assert issubclass(Guardian, MeleeUnit)
    assert issubclass(Ripper, MeleeUnit)
    assert issubclass(Brute, MeleeUnit)
    assert issubclass(Marksman, DeadZoneRangedUnit)
    assert issubclass(Spitter, DeadZoneRangedUnit)
    assert issubclass(Arclight, ArtilleryUnit)


def test_caster_and_artillery_are_independent_semantics() -> None:
    """Artillery must not acquire future caster energy or ability behavior."""
    assert issubclass(CasterUnit, Unit)
    assert issubclass(ArtilleryUnit, Unit)
    assert not issubclass(ArtilleryUnit, CasterUnit)
    assert not issubclass(CasterUnit, ArtilleryUnit)


def test_shared_content_classes_use_semantic_bases() -> None:
    """Restored content names are concrete leaves, never behavior parents."""
    assert entity_exports.Knight is Knight
    assert entity_exports.Archer is Archer
    assert entity_exports.Mage is Mage
    assert Knight.__bases__ == (MeleeUnit,)
    assert Archer.__bases__ == (DeadZoneRangedUnit,)
    assert Mage.__bases__ == (CasterUnit,)
