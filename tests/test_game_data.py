"""Tests for static gameplay data."""

from __future__ import annotations

from rts_nano.content import CONTENT
from rts_nano.game.data import (
    BUILDING_SPECS,
    CONSTRUCTION_REFUND_RATIO,
    PRODUCTION_REFUND_RATIO,
    RESOURCE_KINDS,
    UNIT_SPECS,
)


def test_game_data_defines_current_worker_production() -> None:
    """Peasant production has one canonical data definition."""
    peasant = UNIT_SPECS["peasant"]
    base = BUILDING_SPECS["base"]

    assert RESOURCE_KINDS == ("wood", "gold")
    assert PRODUCTION_REFUND_RATIO == 0.75
    assert CONSTRUCTION_REFUND_RATIO == 0.75
    assert peasant.cost.wood == 50
    assert peasant.production_frames == 60
    assert tuple(str(item.id) for item in CONTENT.producers_for_unit("peasant")) == ("base",)
    assert base.provides_population == 10
    assert "peasant" in base.produces


def test_game_data_defines_basic_military_production() -> None:
    """Each faction's tier-1 military building owns its unit production."""
    arsenal = BUILDING_SPECS["arsenal"]
    pit = BUILDING_SPECS["pit"]

    assert tuple(str(item.id) for item in CONTENT.producers_for_unit("guardian")) == ("arsenal",)
    assert tuple(str(item.id) for item in CONTENT.producers_for_unit("marksman")) == ("arsenal",)
    assert UNIT_SPECS["guardian"].cost.wood == 110
    assert UNIT_SPECS["guardian"].cost.gold == 55
    assert arsenal.produces == ("knight", "archer", "marksman", "guardian")
    assert pit.produces == ("knight", "archer", "ripper", "spitter")
    assert arsenal.faction == "AEGIS"
    assert pit.faction == "RUST"


def test_game_data_defines_faction_tech_gates() -> None:
    """Advanced production buildings require their faction's tier-1 building."""
    assert BUILDING_SPECS["spire"].requires == ("arsenal",)
    assert BUILDING_SPECS["chem_vat"].requires == ("pit",)
    assert tuple(str(item.id) for item in CONTENT.producers_for_unit("arclight")) == ("spire",)
    assert tuple(str(item.id) for item in CONTENT.producers_for_unit("brute")) == ("chem_vat",)
    assert tuple(str(item.id) for item in CONTENT.producers_for_unit("mage")) == ("chem_vat", "spire")


def test_game_data_sketches_minimal_full_rts_roster() -> None:
    """The data layer names the minimal current and near-term RTS roles."""
    assert BUILDING_SPECS["house"].provides_population == 6
    unit_roles = {spec.role for spec in UNIT_SPECS.values()}
    assert "worker" in unit_roles
    assert {"tank", "ranged", "artillery"} <= unit_roles  # AEGIS elite line
    assert {"swarm", "heavy"} <= unit_roles  # RUST swarm line
    assert {spec.role for spec in BUILDING_SPECS.values()} >= {
        "dropoff_production",
        "population",
        "military_production",
        "advanced_production",
        "defense",
    }
