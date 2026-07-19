"""Tests for stable core-domain vocabulary."""

from rts_nano.game.types import CombatRole, ContentId, EntityCategory, EntityId, FactionId, TeamId


def test_domain_identifiers_preserve_serializable_primitive_values() -> None:
    """Domain IDs remain lightweight strings/integers at runtime."""
    assert ContentId("guardian") == "guardian"
    assert EntityId(7) == 7
    assert TeamId("player_one") == "player_one"
    assert FactionId("AEGIS") == "AEGIS"


def test_domain_categories_have_stable_serialized_values() -> None:
    """Generic entity indexes and definitions share explicit category vocabulary."""
    assert tuple(EntityCategory) == (
        EntityCategory.UNIT,
        EntityCategory.BUILDING,
        EntityCategory.RESOURCE,
    )
    assert CombatRole.ARTILLERY == "artillery"
