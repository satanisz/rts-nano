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
    gold: int = 0


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
    faction: str = "any"


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
    faction: str = "any"
    requires: tuple[str, ...] = ()


RESOURCE_KINDS: tuple[str, str] = ("wood", "gold")
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
    # --- AEGIS (Blue): precision / armored / ranged elite ---
    "marksman": UnitSpec(
        key="marksman",
        display_name="Marksman",
        role="ranged",
        cost=ResourceCost(wood=90, gold=35),
        production_frames=120,
        population=2,
        produced_at="arsenal",
        roster_attribute="archers",
        faction="AEGIS",
    ),
    "guardian": UnitSpec(
        key="guardian",
        display_name="Guardian",
        role="tank",
        cost=ResourceCost(wood=110, gold=55),
        production_frames=150,
        population=3,
        produced_at="arsenal",
        roster_attribute="knights",
        faction="AEGIS",
    ),
    "arclight": UnitSpec(
        key="arclight",
        display_name="Arclight",
        role="artillery",
        cost=ResourceCost(wood=80, gold=130),
        production_frames=180,
        population=3,
        produced_at="spire",
        roster_attribute="mages",
        faction="AEGIS",
    ),
    # --- RUST (Red): cheap / fast / expendable swarm ---
    "ripper": UnitSpec(
        key="ripper",
        display_name="Ripper",
        role="swarm",
        cost=ResourceCost(wood=55, gold=10),
        production_frames=90,
        population=1,
        produced_at="pit",
        roster_attribute="knights",
        faction="RUST",
    ),
    "spitter": UnitSpec(
        key="spitter",
        display_name="Spitter",
        role="ranged",
        cost=ResourceCost(wood=60, gold=20),
        production_frames=100,
        population=1,
        produced_at="pit",
        roster_attribute="archers",
        faction="RUST",
    ),
    "brute": UnitSpec(
        key="brute",
        display_name="Brute",
        role="heavy",
        cost=ResourceCost(wood=120, gold=40),
        production_frames=180,
        population=3,
        produced_at="chem_vat",
        roster_attribute="knights",
        faction="RUST",
    ),
}

BUILDING_SPECS: dict[str, BuildingSpec] = {
    "base": BuildingSpec(
        key="base",
        display_name="Base",
        role="dropoff_production",
        cost=ResourceCost(wood=400, gold=100),
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
    # --- AEGIS (Blue) ---
    "arsenal": BuildingSpec(
        key="arsenal",
        display_name="Arsenal",
        role="military_production",
        cost=ResourceCost(wood=220, gold=60),
        build_frames=360,
        footprint=(3, 3),
        produces=("marksman", "guardian"),
        faction="AEGIS",
    ),
    "spire": BuildingSpec(
        key="spire",
        display_name="Spire",
        role="advanced_production",
        cost=ResourceCost(wood=200, gold=150),
        build_frames=420,
        footprint=(3, 3),
        produces=("arclight",),
        faction="AEGIS",
        requires=("arsenal",),
    ),
    "bastion": BuildingSpec(
        key="bastion",
        display_name="Bastion",
        role="defense",
        cost=ResourceCost(wood=150, gold=80),
        build_frames=240,
        footprint=(2, 2),
        faction="AEGIS",
    ),
    # --- RUST (Red) ---
    "pit": BuildingSpec(
        key="pit",
        display_name="Pit",
        role="military_production",
        cost=ResourceCost(wood=180, gold=40),
        build_frames=300,
        footprint=(3, 3),
        produces=("ripper", "spitter"),
        faction="RUST",
    ),
    "chem_vat": BuildingSpec(
        key="chem_vat",
        display_name="Chem-Vat",
        role="advanced_production",
        cost=ResourceCost(wood=160, gold=120),
        build_frames=360,
        footprint=(3, 3),
        produces=("brute",),
        faction="RUST",
        requires=("pit",),
    ),
    "spiker": BuildingSpec(
        key="spiker",
        display_name="Spiker",
        role="defense",
        cost=ResourceCost(wood=120, gold=60),
        build_frames=200,
        footprint=(2, 2),
        faction="RUST",
    ),
}


FACTION_BY_TEAM: dict[str, str] = {"Blue": "AEGIS", "Red": "RUST"}


def faction_for_team(team: object) -> str:
    """Return the faction a team plays (Blue=AEGIS, Red=RUST), else ``any``."""
    team_name = str(getattr(team, "value", team))
    return FACTION_BY_TEAM.get(team_name, "any")


def units_for_faction(faction: str) -> dict[str, UnitSpec]:
    """Return unit specs available to a faction (plus faction-neutral units)."""
    return {key: spec for key, spec in UNIT_SPECS.items() if spec.faction in {"any", faction}}


def buildings_for_faction(faction: str) -> dict[str, BuildingSpec]:
    """Return building specs available to a faction (plus faction-neutral ones)."""
    return {key: spec for key, spec in BUILDING_SPECS.items() if spec.faction in {"any", faction}}


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
