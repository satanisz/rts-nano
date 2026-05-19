"""Static gameplay data for units, buildings, economy, and production.

This module is the first small step toward a data-driven rules layer. Runtime
systems should read costs, timings, and population values from here instead of
hard-coding them in UI or order helpers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResourceCost:
    """Resource cost paid by a team economy bank."""

    wood: int = 0
    cristal: int = 0


@dataclass(frozen=True, slots=True)
class UnitSpec:
    """Design data for one trainable unit type."""

    key: str
    display_name: str
    role: str
    cost: ResourceCost
    production_frames: int
    population: int
    produced_at: str
    roster_attribute: str


@dataclass(frozen=True, slots=True)
class BuildingSpec:
    """Design data for one building type."""

    key: str
    display_name: str
    role: str
    cost: ResourceCost
    build_frames: int
    footprint: tuple[int, int]
    provides_population: int = 0
    produces: tuple[str, ...] = ()


RESOURCE_KINDS: tuple[str, str] = ("wood", "cristal")
PRODUCTION_REFUND_RATIO = 0.75
CONSTRUCTION_REFUND_RATIO = 0.75

UNIT_SPECS: dict[str, UnitSpec] = {
    "peasant": UnitSpec(
        key="peasant",
        display_name="Peasant",
        role="worker",
        cost=ResourceCost(wood=50),
        production_frames=60,
        population=1,
        produced_at="base",
        roster_attribute="peasents",
    ),
    "knight": UnitSpec(
        key="knight",
        display_name="Knight",
        role="melee",
        cost=ResourceCost(wood=100, cristal=25),
        production_frames=120,
        population=2,
        produced_at="barracks",
        roster_attribute="knights",
    ),
    "archer": UnitSpec(
        key="archer",
        display_name="Archer",
        role="ranged",
        cost=ResourceCost(wood=80, cristal=40),
        production_frames=120,
        population=2,
        produced_at="barracks",
        roster_attribute="archers",
    ),
    "mage": UnitSpec(
        key="mage",
        display_name="Mage",
        role="caster",
        cost=ResourceCost(wood=70, cristal=120),
        production_frames=180,
        population=3,
        produced_at="mage_tower",
        roster_attribute="mages",
    ),
}

BUILDING_SPECS: dict[str, BuildingSpec] = {
    "base": BuildingSpec(
        key="base",
        display_name="Base",
        role="dropoff_production",
        cost=ResourceCost(wood=400, cristal=100),
        build_frames=300,
        footprint=(3, 3),
        provides_population=10,
        produces=("peasant",),
    ),
    "house": BuildingSpec(
        key="house",
        display_name="House",
        role="population",
        cost=ResourceCost(wood=80),
        build_frames=180,
        footprint=(2, 2),
        provides_population=6,
    ),
    "barracks": BuildingSpec(
        key="barracks",
        display_name="Barracks",
        role="military_production",
        cost=ResourceCost(wood=220, cristal=60),
        build_frames=360,
        footprint=(3, 3),
        produces=("knight", "archer"),
    ),
    "mage_tower": BuildingSpec(
        key="mage_tower",
        display_name="Mage Tower",
        role="advanced_production",
        cost=ResourceCost(wood=180, cristal=180),
        build_frames=420,
        footprint=(3, 3),
        produces=("mage",),
    ),
    "tower": BuildingSpec(
        key="tower",
        display_name="Tower",
        role="defense",
        cost=ResourceCost(wood=150, cristal=80),
        build_frames=240,
        footprint=(2, 2),
    ),
}


def get_unit_spec(unit_type: str) -> UnitSpec:
    """Return unit design data or raise a clear error for unknown unit types."""
    try:
        return UNIT_SPECS[unit_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported unit type: {unit_type}") from exc


def get_building_spec(building_type: str) -> BuildingSpec:
    """Return building design data or raise a clear error for unknown buildings."""
    try:
        return BUILDING_SPECS[building_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported building type: {building_type}") from exc
