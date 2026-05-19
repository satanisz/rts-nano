"""Tests for static gameplay data."""

from __future__ import annotations

from rts_nano.game.data import (
    BUILDING_SPECS,
    DEFAULT_POPULATION_CAP,
    PRODUCTION_REFUND_RATIO,
    RESOURCE_KINDS,
    UNIT_SPECS,
)


def test_game_data_defines_current_worker_production() -> None:
    """Peasant production has one canonical data definition."""
    peasant = UNIT_SPECS["peasant"]
    base = BUILDING_SPECS["base"]

    assert RESOURCE_KINDS == ("wood", "cristal")
    assert DEFAULT_POPULATION_CAP == 50
    assert PRODUCTION_REFUND_RATIO == 0.75
    assert peasant.cost.wood == 50
    assert peasant.production_frames == 60
    assert peasant.produced_at == "base"
    assert "peasant" in base.produces


def test_game_data_defines_basic_military_production() -> None:
    """Knight and archer production is owned by barracks data."""
    barracks = BUILDING_SPECS["barracks"]

    assert UNIT_SPECS["knight"].produced_at == "barracks"
    assert UNIT_SPECS["archer"].produced_at == "barracks"
    assert UNIT_SPECS["knight"].cost.wood == 100
    assert UNIT_SPECS["knight"].cost.cristal == 25
    assert barracks.produces == ("knight", "archer")


def test_game_data_sketches_minimal_full_rts_roster() -> None:
    """The data layer names the minimal current and near-term RTS roles."""
    assert {spec.role for spec in UNIT_SPECS.values()} >= {"worker", "melee", "ranged", "caster"}
    assert {spec.role for spec in BUILDING_SPECS.values()} >= {
        "dropoff_production",
        "population",
        "military_production",
        "advanced_production",
        "defense",
    }
