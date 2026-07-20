"""Validated single source of truth for RTS Nano gameplay content."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

from rts_nano.content.definitions import (
    AbilityDefinition,
    AttackKind,
    BuildingDefinition,
    FactionDefinition,
    ResourceCost,
    ResourceDefinition,
    UnitDefinition,
    UpgradeDefinition,
)
from rts_nano.game.types import ContentId, FactionId, ModifierStat

AEGIS_SHIELD_REGEN = 8
AEGIS_SHIELD_REGEN_DELAY = 240
PRODUCTION_REFUND_RATIO = 0.75
CONSTRUCTION_REFUND_RATIO = 0.75


class ContentRegistry:
    """Validated immutable-by-convention lookup for all gameplay definitions."""

    def __init__(
        self,
        *,
        units: Iterable[UnitDefinition],
        buildings: Iterable[BuildingDefinition],
        resources: Iterable[ResourceDefinition],
        factions: Iterable[FactionDefinition],
        upgrades: Iterable[UpgradeDefinition] = (),
        abilities: Iterable[AbilityDefinition] = (),
    ) -> None:
        """Build indexes and reject inconsistent content graphs."""
        self.units = self._unique_by_id(units, "unit")
        self.buildings = self._unique_by_id(buildings, "building")
        self.resources = self._unique_by_id(resources, "resource")
        self.factions = self._unique_by_id(factions, "faction")
        self.upgrades = self._unique_by_id(upgrades, "upgrade")
        self.abilities = self._unique_by_id(abilities, "ability")
        self._validate()
        self._producers_by_unit = self._build_producer_index()

    @staticmethod
    def _unique_by_id[
        T: UnitDefinition
        | BuildingDefinition
        | ResourceDefinition
        | FactionDefinition
        | UpgradeDefinition
        | AbilityDefinition
    ](definitions: Iterable[T], label: str) -> MappingProxyType[str, T]:
        result: dict[str, T] = {}
        for definition in definitions:
            key = str(definition.id)
            if key in result:
                raise ValueError(f"Duplicate {label} id: {key}")
            result[key] = definition
        return MappingProxyType(result)

    def get_unit(self, content_id: str | ContentId) -> UnitDefinition:
        """Return a unit definition or raise a clear unsupported-content error."""
        try:
            return self.units[str(content_id)]
        except KeyError as exc:
            raise ValueError(f"Unsupported unit type: {content_id}") from exc

    def get_building(self, content_id: str | ContentId) -> BuildingDefinition:
        """Return a building definition or raise a clear unsupported-content error."""
        try:
            return self.buildings[str(content_id)]
        except KeyError as exc:
            raise ValueError(f"Unsupported building type: {content_id}") from exc

    def get_resource(self, content_id: str | ContentId) -> ResourceDefinition:
        """Return a resource definition or raise a clear unsupported-content error."""
        try:
            return self.resources[str(content_id)]
        except KeyError as exc:
            raise ValueError(f"Unsupported resource type: {content_id}") from exc

    def producers_for_unit(self, content_id: str | ContentId) -> tuple[BuildingDefinition, ...]:
        """Return valid producers in canonical building-ID order."""
        unit_id = str(content_id)
        if unit_id not in self.units:
            raise ValueError(f"Unsupported unit type: {content_id}")
        return self._producers_by_unit[unit_id]

    def get_upgrade(self, upgrade_id: str) -> UpgradeDefinition:
        """Return an upgrade definition or raise a clear unsupported-tech error."""
        try:
            return self.upgrades[upgrade_id]
        except KeyError as exc:
            raise ValueError(f"Unsupported upgrade: {upgrade_id}") from exc

    def get_ability(self, ability_id: str) -> AbilityDefinition:
        """Return an active ability definition or raise a clear error."""
        try:
            return self.abilities[ability_id]
        except KeyError as exc:
            raise ValueError(f"Unsupported ability: {ability_id}") from exc

    def units_for_faction(self, faction_id: str | FactionId) -> dict[str, UnitDefinition]:
        """Return shared and faction-specific unit definitions."""
        faction = self._get_faction(faction_id)
        return {str(content_id): self.get_unit(content_id) for content_id in faction.unit_ids}

    def buildings_for_faction(self, faction_id: str | FactionId) -> dict[str, BuildingDefinition]:
        """Return shared and faction-specific building definitions."""
        faction = self._get_faction(faction_id)
        return {str(content_id): self.get_building(content_id) for content_id in faction.building_ids}

    def _get_faction(self, faction_id: str | FactionId) -> FactionDefinition:
        try:
            return self.factions[str(faction_id)]
        except KeyError as exc:
            raise ValueError(f"Unsupported faction: {faction_id}") from exc

    def _validate(self) -> None:
        all_ids = (*self.units, *self.buildings, *self.resources)
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Content ids must be unique across all categories")

        for unit in self.units.values():
            if min(unit.production_frames, unit.population, unit.size, unit.max_life, unit.vision_range) <= 0:
                raise ValueError(f"Unit {unit.id} has non-positive core values")
            if unit.radius <= 0 or unit.speed <= 0 or unit.attack_speed <= 0:
                raise ValueError(f"Unit {unit.id} has non-positive movement or combat values")
            if min(unit.cost.wood, unit.cost.gold, unit.attack_damage, unit.attack_modifier) < 0:
                raise ValueError(f"Unit {unit.id} has negative costs or combat values")
            if min(unit.build_rate, unit.repair_rate) < 0:
                raise ValueError(f"Unit {unit.id} has negative worker rates")
            for required in unit.requires:
                if str(required) not in self.buildings:
                    raise ValueError(f"Unit {unit.id} requires missing building {required}")

        for building in self.buildings.values():
            if (
                min(building.build_frames, *building.footprint, building.size, building.max_life, building.vision_range)
                <= 0
            ):
                raise ValueError(f"Building {building.id} has non-positive core values")
            if building.radius <= 0:
                raise ValueError(f"Building {building.id} has non-positive radius")
            if building.repair_hp_per_wood <= 0:
                raise ValueError(f"Building {building.id} has non-positive repair efficiency")
            if min(building.cost.wood, building.cost.gold, building.attack_damage, building.attack_modifier) < 0:
                raise ValueError(f"Building {building.id} has negative costs or combat values")
            for required in building.requires:
                if str(required) not in self.buildings:
                    raise ValueError(f"Building {building.id} requires missing building {required}")
            if len(building.produces) != len(set(building.produces)):
                raise ValueError(f"Building {building.id} contains duplicate production links")
            for produced in building.produces:
                unit = self.units.get(str(produced))
                if unit is None:
                    raise ValueError(f"Building {building.id} produces missing unit {produced}")
                if unit.faction is not None and building.faction != unit.faction:
                    raise ValueError(f"Building {building.id} cannot produce foreign unit {produced}")

        produced_unit_ids = {str(unit_id) for building in self.buildings.values() for unit_id in building.produces}
        missing_producers = sorted(set(self.units) - produced_unit_ids)
        if missing_producers:
            raise ValueError(f"Units have no producer: {missing_producers}")

        self._validate_tech_cycles()
        self._validate_factions()
        self._validate_upgrades()
        self._validate_abilities()

        for resource in self.resources.values():
            if resource.amount <= 0 or resource.size <= 0 or resource.radius <= 0:
                raise ValueError(f"Resource {resource.id} has non-positive amount, size, or radius")

    def _validate_tech_cycles(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(building_id: str) -> None:
            if building_id in visiting:
                raise ValueError(f"Tech tree contains a cycle at {building_id}")
            if building_id in visited:
                return
            visiting.add(building_id)
            for requirement in self.buildings[building_id].requires:
                visit(str(requirement))
            visiting.remove(building_id)
            visited.add(building_id)

        for building_id in self.buildings:
            visit(building_id)

    def _build_producer_index(self) -> MappingProxyType[str, tuple[BuildingDefinition, ...]]:
        """Derive the reverse graph once; building definitions remain authoritative."""
        result: dict[str, list[BuildingDefinition]] = {unit_id: [] for unit_id in self.units}
        for building in sorted(self.buildings.values(), key=lambda definition: str(definition.id)):
            for unit_id in building.produces:
                result[str(unit_id)].append(building)
        return MappingProxyType({unit_id: tuple(producers) for unit_id, producers in result.items()})

    def _validate_factions(self) -> None:
        assigned_units: set[str] = set()
        assigned_buildings: set[str] = set()
        for faction in self.factions.values():
            if len(faction.unit_ids) != len(set(faction.unit_ids)):
                raise ValueError(f"Faction {faction.id} contains duplicate units")
            if len(faction.building_ids) != len(set(faction.building_ids)):
                raise ValueError(f"Faction {faction.id} contains duplicate buildings")
            for content_id in faction.unit_ids:
                definition = self.get_unit(content_id)
                if definition.faction is not None and definition.faction != faction.id:
                    raise ValueError(f"Faction {faction.id} includes foreign unit {content_id}")
                assigned_units.add(str(content_id))
            for content_id in faction.building_ids:
                definition = self.get_building(content_id)
                if definition.faction is not None and definition.faction != faction.id:
                    raise ValueError(f"Faction {faction.id} includes foreign building {content_id}")
                assigned_buildings.add(str(content_id))

        faction_units = {key for key, definition in self.units.items() if definition.faction is not None}
        faction_buildings = {key for key, definition in self.buildings.items() if definition.faction is not None}
        if faction_units - assigned_units:
            raise ValueError(f"Faction units missing from rosters: {sorted(faction_units - assigned_units)}")
        if faction_buildings - assigned_buildings:
            raise ValueError(
                f"Faction buildings missing from rosters: {sorted(faction_buildings - assigned_buildings)}"
            )

    def _validate_upgrades(self) -> None:
        """Reject invalid ownership, modifier, conflict, and prerequisite graphs."""
        valid_stats = set(ModifierStat)
        for upgrade in self.upgrades.values():
            if str(upgrade.faction) not in self.factions:
                raise ValueError(f"Upgrade {upgrade.id} references missing faction {upgrade.faction}")
            if upgrade.research_frames <= 0 or min(upgrade.cost.wood, upgrade.cost.gold) < 0:
                raise ValueError(f"Upgrade {upgrade.id} has invalid cost or duration")
            if not upgrade.research_at or len(upgrade.research_at) != len(set(upgrade.research_at)):
                raise ValueError(f"Upgrade {upgrade.id} requires unique research buildings")
            for building_id in (*upgrade.research_at, *upgrade.required_buildings):
                building = self.buildings.get(str(building_id))
                if building is None:
                    raise ValueError(f"Upgrade {upgrade.id} references missing building {building_id}")
                if building.faction not in {None, upgrade.faction}:
                    raise ValueError(f"Upgrade {upgrade.id} references foreign building {building_id}")
            for content_id in upgrade.affected_content:
                definition = self.units.get(str(content_id)) or self.buildings.get(str(content_id))
                if definition is None:
                    raise ValueError(f"Upgrade {upgrade.id} affects missing content {content_id}")
                if definition.faction not in {None, upgrade.faction}:
                    raise ValueError(f"Upgrade {upgrade.id} affects foreign content {content_id}")
            if len(upgrade.affected_content) != len(set(upgrade.affected_content)):
                raise ValueError(f"Upgrade {upgrade.id} contains duplicate affected content")
            modifier_stats = [modifier.stat for modifier in upgrade.modifiers]
            if len(modifier_stats) != len(set(modifier_stats)):
                raise ValueError(f"Upgrade {upgrade.id} modifies one stat more than once")
            for modifier in upgrade.modifiers:
                if modifier.stat not in valid_stats or modifier.denominator <= 0 or modifier.numerator < 0:
                    raise ValueError(f"Upgrade {upgrade.id} has invalid modifier for {modifier.stat}")
            for related_id in (*upgrade.required_upgrades, *upgrade.conflicts):
                related = self.upgrades.get(str(related_id))
                if related is None:
                    raise ValueError(f"Upgrade {upgrade.id} references missing upgrade {related_id}")
                if related.faction != upgrade.faction:
                    raise ValueError(f"Upgrade {upgrade.id} references foreign upgrade {related_id}")
            for conflict_id in upgrade.conflicts:
                if upgrade.id not in self.upgrades[str(conflict_id)].conflicts:
                    raise ValueError(f"Upgrade conflict {upgrade.id}/{conflict_id} must be symmetric")
            for ability_id in upgrade.granted_abilities:
                if str(ability_id) not in self.abilities:
                    raise ValueError(f"Upgrade {upgrade.id} grants missing ability {ability_id}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(upgrade_id: str) -> None:
            if upgrade_id in visiting:
                raise ValueError(f"Upgrade tree contains a cycle at {upgrade_id}")
            if upgrade_id in visited:
                return
            visiting.add(upgrade_id)
            for requirement in self.upgrades[upgrade_id].required_upgrades:
                visit(str(requirement))
            visiting.remove(upgrade_id)
            visited.add(upgrade_id)

        for upgrade_id in self.upgrades:
            visit(upgrade_id)

        groups: dict[str, set[str]] = {}
        for upgrade in self.upgrades.values():
            if upgrade.exclusive_group is not None:
                groups.setdefault(str(upgrade.exclusive_group), set()).add(str(upgrade.faction))
        if any(len(factions) != 1 for factions in groups.values()):
            raise ValueError("Upgrade exclusivity groups cannot span factions")

    def _validate_abilities(self) -> None:
        for ability in self.abilities.values():
            if (
                min(
                    ability.energy_cost,
                    ability.cooldown_frames,
                    ability.cast_range,
                    ability.duration_frames,
                    ability.radius,
                    ability.magnitude,
                )
                < 0
            ):
                raise ValueError(f"Ability {ability.id} has negative values")
            if ability.max_targets <= 0:
                raise ValueError(f"Ability {ability.id} has no valid targets")


UNIT_DEFINITIONS = (
    UnitDefinition(
        id=ContentId("peasant"),
        display_name="Peasant",
        role="worker",
        faction=None,
        visual_key="peasant",
        behavior="worker",
        cost=ResourceCost(wood=50),
        production_frames=60,
        population=1,
        requires=(),
        size=30,
        radius=10.0,
        speed=2.0,
        max_carry=10,
        max_life=5,
        vision_range=250,
        attack_damage=3,
        attack_modifier=0,
        attack_range=0,
        attack_speed=1.0,
        attack_kinds=(AttackKind.MELEE,),
        build_rate=1,
        repair_rate=2,
    ),
    UnitDefinition(
        id=ContentId("knight"),
        display_name="Knight",
        role="melee",
        faction=None,
        visual_key="knight",
        behavior="melee",
        cost=ResourceCost(wood=75, gold=25),
        production_frames=110,
        population=2,
        requires=(),
        size=40,
        radius=13.0,
        speed=2.2,
        max_carry=2,
        max_life=100,
        vision_range=250,
        attack_damage=8,
        attack_modifier=0,
        attack_range=5,
        attack_speed=1.0,
        attack_kinds=(AttackKind.MELEE,),
    ),
    UnitDefinition(
        id=ContentId("archer"),
        display_name="Archer",
        role="ranged",
        faction=None,
        visual_key="archer",
        behavior="ranged",
        cost=ResourceCost(wood=70, gold=30),
        production_frames=110,
        population=2,
        requires=(),
        size=40,
        radius=13.0,
        speed=2.3,
        max_carry=2,
        max_life=55,
        vision_range=250,
        attack_damage=7,
        attack_modifier=0,
        attack_range=50,
        attack_speed=1.0,
        attack_kinds=(AttackKind.MELEE, AttackKind.RANGED),
        melee_attack_range=10,
        ranged_min_attack_range=80,
        ranged_attack_range=170,
    ),
    UnitDefinition(
        id=ContentId("mage"),
        display_name="Mage",
        role="caster",
        faction=None,
        visual_key="mage",
        behavior="caster",
        cost=ResourceCost(wood=75, gold=100),
        production_frames=160,
        population=3,
        requires=(),
        size=40,
        radius=13.0,
        speed=1.8,
        max_carry=1,
        max_life=55,
        vision_range=280,
        attack_damage=10,
        attack_modifier=0,
        attack_range=220,
        attack_speed=1.2,
        attack_kinds=(AttackKind.RANGED,),
        energy_max=100,
        energy_regen_numerator=1,
        energy_regen_denominator=6,
    ),
    UnitDefinition(
        id=ContentId("marksman"),
        display_name="Marksman",
        role="ranged",
        faction=FactionId("AEGIS"),
        visual_key="marksman",
        behavior="ranged",
        cost=ResourceCost(wood=90, gold=35),
        production_frames=120,
        population=2,
        requires=(),
        size=40,
        radius=13.0,
        speed=2.2,
        max_carry=2,
        max_life=70,
        vision_range=250,
        attack_damage=9,
        attack_modifier=0,
        attack_range=50,
        attack_speed=1.0,
        attack_kinds=(AttackKind.MELEE, AttackKind.RANGED),
        shield_modifier=1,
        shield_max=30,
        shield_regen=AEGIS_SHIELD_REGEN,
        shield_regen_delay=AEGIS_SHIELD_REGEN_DELAY,
        melee_attack_range=10,
        ranged_min_attack_range=100,
        ranged_attack_range=210,
    ),
    UnitDefinition(
        id=ContentId("guardian"),
        display_name="Guardian",
        role="tank",
        faction=FactionId("AEGIS"),
        visual_key="guardian",
        behavior="melee",
        cost=ResourceCost(wood=110, gold=55),
        production_frames=150,
        population=3,
        requires=(),
        size=40,
        radius=13.0,
        speed=1.9,
        max_carry=3,
        max_life=150,
        vision_range=250,
        attack_damage=8,
        attack_modifier=0,
        attack_range=5,
        attack_speed=1.0,
        attack_kinds=(AttackKind.MELEE,),
        shield_modifier=4,
        shield_max=60,
        shield_regen=AEGIS_SHIELD_REGEN,
        shield_regen_delay=AEGIS_SHIELD_REGEN_DELAY,
    ),
    UnitDefinition(
        id=ContentId("arclight"),
        display_name="Arclight",
        role="artillery",
        faction=FactionId("AEGIS"),
        visual_key="arclight",
        behavior="artillery",
        cost=ResourceCost(wood=80, gold=130),
        production_frames=180,
        population=3,
        requires=(),
        size=40,
        radius=13.0,
        speed=1.4,
        max_carry=1,
        max_life=40,
        vision_range=250,
        attack_damage=16,
        attack_modifier=0,
        attack_range=520,
        attack_speed=1.3,
        attack_kinds=(AttackKind.RANGED,),
        shield_max=20,
        shield_regen=AEGIS_SHIELD_REGEN,
        shield_regen_delay=AEGIS_SHIELD_REGEN_DELAY,
        splash_radius=60,
    ),
    UnitDefinition(
        id=ContentId("ripper"),
        display_name="Ripper",
        role="swarm",
        faction=FactionId("RUST"),
        visual_key="ripper",
        behavior="melee",
        cost=ResourceCost(wood=55, gold=10),
        production_frames=90,
        population=1,
        requires=(),
        size=40,
        radius=13.0,
        speed=3.0,
        max_carry=3,
        max_life=45,
        vision_range=250,
        attack_damage=6,
        attack_modifier=0,
        attack_range=5,
        attack_speed=1.0,
        attack_kinds=(AttackKind.MELEE,),
        frenzy=True,
    ),
    UnitDefinition(
        id=ContentId("spitter"),
        display_name="Spitter",
        role="ranged",
        faction=FactionId("RUST"),
        visual_key="spitter",
        behavior="ranged",
        cost=ResourceCost(wood=60, gold=20),
        production_frames=100,
        population=1,
        requires=(),
        size=40,
        radius=13.0,
        speed=2.4,
        max_carry=2,
        max_life=40,
        vision_range=250,
        attack_damage=6,
        attack_modifier=0,
        attack_range=50,
        attack_speed=1.0,
        attack_kinds=(AttackKind.MELEE, AttackKind.RANGED),
        poison_damage=2,
        poison_duration=90,
        melee_attack_range=10,
        ranged_min_attack_range=60,
        ranged_attack_range=130,
    ),
    UnitDefinition(
        id=ContentId("brute"),
        display_name="Brute",
        role="heavy",
        faction=FactionId("RUST"),
        visual_key="brute",
        behavior="melee",
        cost=ResourceCost(wood=120, gold=40),
        production_frames=180,
        population=3,
        requires=(),
        size=40,
        radius=13.0,
        speed=1.8,
        max_carry=3,
        max_life=200,
        vision_range=250,
        attack_damage=14,
        attack_modifier=0,
        attack_range=5,
        attack_speed=1.1,
        attack_kinds=(AttackKind.MELEE,),
        shield_modifier=1,
        poison_damage=3,
        poison_duration=120,
        frenzy=True,
    ),
)

BUILDING_DEFINITIONS = (
    BuildingDefinition(
        id=ContentId("base"),
        display_name="Base",
        role="dropoff_production",
        faction=None,
        visual_key="base",
        behavior="headquarters",
        cost=ResourceCost(wood=400, gold=100),
        build_frames=300,
        constructable=False,
        footprint=(3, 3),
        size=80,
        radius=20.0,
        max_life=500,
        vision_range=400,
        provides_population=10,
        produces=(ContentId("peasant"),),
    ),
    BuildingDefinition(
        id=ContentId("house"),
        display_name="House",
        role="population",
        faction=None,
        visual_key="house",
        behavior="population",
        cost=ResourceCost(wood=80),
        build_frames=180,
        constructable=True,
        footprint=(2, 2),
        size=80,
        radius=20.0,
        max_life=500,
        vision_range=400,
        provides_population=6,
    ),
    BuildingDefinition(
        id=ContentId("arsenal"),
        display_name="Arsenal",
        role="military_production",
        faction=FactionId("AEGIS"),
        visual_key="arsenal",
        behavior="production",
        cost=ResourceCost(wood=220, gold=60),
        build_frames=360,
        constructable=True,
        footprint=(3, 3),
        size=80,
        radius=20.0,
        max_life=500,
        vision_range=400,
        produces=(ContentId("knight"), ContentId("archer"), ContentId("marksman"), ContentId("guardian")),
    ),
    BuildingDefinition(
        id=ContentId("spire"),
        display_name="Spire",
        role="advanced_production",
        faction=FactionId("AEGIS"),
        visual_key="spire",
        behavior="production",
        cost=ResourceCost(wood=200, gold=150),
        build_frames=420,
        constructable=True,
        footprint=(3, 3),
        size=80,
        radius=20.0,
        max_life=500,
        vision_range=400,
        produces=(ContentId("mage"), ContentId("arclight")),
        requires=(ContentId("arsenal"),),
    ),
    BuildingDefinition(
        id=ContentId("bastion"),
        display_name="Bastion",
        role="defense",
        faction=FactionId("AEGIS"),
        visual_key="bastion",
        behavior="tower",
        cost=ResourceCost(wood=150, gold=80),
        build_frames=240,
        constructable=True,
        footprint=(2, 2),
        size=56,
        radius=18.0,
        max_life=350,
        vision_range=400,
        attack_damage=12,
        attack_range=200,
        attack_speed=1.0,
        attack_kind=AttackKind.RANGED,
        shield_max=80,
        shield_regen=AEGIS_SHIELD_REGEN,
        shield_regen_delay=AEGIS_SHIELD_REGEN_DELAY,
    ),
    BuildingDefinition(
        id=ContentId("pit"),
        display_name="Pit",
        role="military_production",
        faction=FactionId("RUST"),
        visual_key="pit",
        behavior="production",
        cost=ResourceCost(wood=180, gold=40),
        build_frames=300,
        constructable=True,
        footprint=(3, 3),
        size=80,
        radius=20.0,
        max_life=500,
        vision_range=400,
        produces=(ContentId("knight"), ContentId("archer"), ContentId("ripper"), ContentId("spitter")),
    ),
    BuildingDefinition(
        id=ContentId("chem_vat"),
        display_name="Chem-Vat",
        role="advanced_production",
        faction=FactionId("RUST"),
        visual_key="chem_vat",
        behavior="production",
        cost=ResourceCost(wood=160, gold=120),
        build_frames=360,
        constructable=True,
        footprint=(3, 3),
        size=80,
        radius=20.0,
        max_life=500,
        vision_range=400,
        produces=(ContentId("mage"), ContentId("brute")),
        requires=(ContentId("pit"),),
    ),
    BuildingDefinition(
        id=ContentId("spiker"),
        display_name="Spiker",
        role="defense",
        faction=FactionId("RUST"),
        visual_key="spiker",
        behavior="tower",
        cost=ResourceCost(wood=120, gold=60),
        build_frames=200,
        constructable=True,
        footprint=(2, 2),
        size=56,
        radius=18.0,
        max_life=250,
        vision_range=400,
        attack_damage=8,
        attack_range=150,
        attack_speed=0.625,
        attack_kind=AttackKind.RANGED,
        poison_damage=2,
        poison_duration=90,
    ),
)

RESOURCE_DEFINITIONS = (
    ResourceDefinition(ContentId("wood"), "Wood", "wood", amount=100, size=15, radius=5.0),
    ResourceDefinition(ContentId("gold"), "Gold", "gold", amount=100, size=15, radius=5.0),
)

FACTION_DEFINITIONS = (
    FactionDefinition(
        id=FactionId("AEGIS"),
        display_name="AEGIS",
        unit_ids=(
            ContentId("peasant"),
            ContentId("knight"),
            ContentId("archer"),
            ContentId("mage"),
            ContentId("marksman"),
            ContentId("guardian"),
            ContentId("arclight"),
        ),
        building_ids=(
            ContentId("base"),
            ContentId("house"),
            ContentId("arsenal"),
            ContentId("spire"),
            ContentId("bastion"),
        ),
    ),
    FactionDefinition(
        id=FactionId("RUST"),
        display_name="RUST",
        unit_ids=(
            ContentId("peasant"),
            ContentId("knight"),
            ContentId("archer"),
            ContentId("mage"),
            ContentId("ripper"),
            ContentId("spitter"),
            ContentId("brute"),
        ),
        building_ids=(
            ContentId("base"),
            ContentId("house"),
            ContentId("pit"),
            ContentId("chem_vat"),
            ContentId("spiker"),
        ),
    ),
)

UPGRADE_DEFINITIONS: tuple[UpgradeDefinition, ...] = ()
ABILITY_DEFINITIONS: tuple[AbilityDefinition, ...] = ()

CONTENT = ContentRegistry(
    units=UNIT_DEFINITIONS,
    buildings=BUILDING_DEFINITIONS,
    resources=RESOURCE_DEFINITIONS,
    factions=FACTION_DEFINITIONS,
    upgrades=UPGRADE_DEFINITIONS,
    abilities=ABILITY_DEFINITIONS,
)
