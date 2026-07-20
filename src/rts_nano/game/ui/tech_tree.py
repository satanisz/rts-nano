"""Registry-derived, presentation-neutral faction technology view model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rts_nano.content import CONTENT, ContentRegistry

if TYPE_CHECKING:
    from rts_nano.game.state import TeamState


@dataclass(frozen=True, slots=True)
class TechTreeEntry:
    """One English research row rendered by the windowed adapter."""

    upgrade_id: str
    name: str
    producer: str
    cost: str
    requirement: str
    status: str
    unlocks: str
    description: str


def build_tech_tree(team: TeamState, registry: ContentRegistry = CONTENT) -> tuple[TechTreeEntry, ...]:
    """Build a stable faction view directly from registry dependencies and team state."""
    faction_upgrades = sorted(
        (upgrade for upgrade in registry.upgrades.values() if upgrade.faction == team.faction_id),
        key=lambda upgrade: (str(upgrade.research_at[0]), str(upgrade.id)),
    )
    completed_groups = {
        registry.get_upgrade(str(upgrade_id)).exclusive_group
        for upgrade_id in team.completed_upgrades
        if registry.get_upgrade(str(upgrade_id)).exclusive_group is not None
    }
    rows: list[TechTreeEntry] = []
    for upgrade in faction_upgrades:
        if team.has_upgrade(str(upgrade.id)):
            status = "COMPLETED"
        elif any(str(item) == str(upgrade.id) for item in team.reserved_upgrades):
            status = "RESEARCHING"
        elif upgrade.exclusive_group in completed_groups:
            status = "LOCKED BY CHOICE"
        elif any(not team.has_upgrade(str(item)) for item in upgrade.required_upgrades):
            status = "REQUIRES RESEARCH"
        else:
            status = "AVAILABLE"
        requirements = [registry.get_upgrade(str(item)).display_name for item in upgrade.required_upgrades]
        if upgrade.exclusive_group is not None:
            requirements.append("exclusive doctrine choice")
        affected = [
            (
                registry.units[str(content_id)].display_name
                if str(content_id) in registry.units
                else registry.buildings[str(content_id)].display_name
            )
            for content_id in upgrade.affected_content
        ]
        abilities = [registry.get_ability(str(item)).display_name for item in upgrade.granted_abilities]
        unlocks = ", ".join((*affected, *abilities)) or "team technology"
        rows.append(
            TechTreeEntry(
                upgrade_id=str(upgrade.id),
                name=upgrade.display_name,
                producer=" / ".join(registry.get_building(item).display_name for item in upgrade.research_at),
                cost=f"{upgrade.cost.wood} Wood, {upgrade.cost.gold} Gold",
                requirement=", ".join(requirements) if requirements else "none",
                status=status,
                unlocks=unlocks,
                description=upgrade.description,
            )
        )
    return tuple(rows)


def validate_technology_graph(registry: ContentRegistry = CONTENT) -> list[str]:
    """Report unreachable producers, orphan grants, and malformed doctrine groups."""
    errors: list[str] = []
    groups: dict[tuple[str, str], list[str]] = {}
    for upgrade in registry.upgrades.values():
        faction = registry.factions[str(upgrade.faction)]
        faction_buildings = {str(item) for item in faction.building_ids}
        for producer in upgrade.research_at:
            if str(producer) not in faction_buildings:
                errors.append(f"{upgrade.id}: producer {producer} is outside faction roster")
        for ability_id in upgrade.granted_abilities:
            if str(ability_id) not in registry.abilities:
                errors.append(f"{upgrade.id}: missing ability {ability_id}")
        if upgrade.exclusive_group is not None:
            key = (str(upgrade.faction), str(upgrade.exclusive_group))
            groups.setdefault(key, []).append(str(upgrade.id))
    for (faction, group), members in groups.items():
        if len(members) != 2:
            errors.append(f"{faction}/{group}: expected two doctrine choices, got {len(members)}")
    return errors
