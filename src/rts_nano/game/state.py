"""Explicit container for core simulation state.

``GameState`` owns the data the simulation systems read and write: team entity
rosters, neutral resources, fog, terrain, map bounds, the current team, the
selection, and the terminal/pause flags. Pure queries over that data
(``all_entities``, ``clamp_to_world``, ``count_units``,
``population_cap_for_team``) live here too.

Keeping state in one object lets systems depend on the data instead of the
``GameManager`` god object, and keeps the manager a thin coordinator. The entity
roster containers live here as well so ``GameState`` has no import cycle with the
manager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rts_nano.game.assets.entities import TeamColor
from rts_nano.game.data import get_building_spec
from rts_nano.game.rules import clamp_point

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Entity
    from rts_nano.game.assets.entities.buildings import Barracks, Base, House, MageTower, Tower
    from rts_nano.game.assets.entities.resources import Gold, Wood
    from rts_nano.game.assets.entities.units import Archer, Knight, Mage, Peasant
    from rts_nano.game.fog import FogOfWar
    from rts_nano.game.terrain import TerrainMap


class EntitiesGroup:
    """Store team-owned entities split into per-class rosters.

    The map JSON groups entities by team, but the runtime further separates unit
    classes into lists for simple counts, UI summaries, and production logic.
    Neutral resources are not stored here; they live in ``ResourcesGroup``.

    Args:
        name: Team associated with the entity collection.
    """

    def __init__(self, name: TeamColor) -> None:
        """Initialize the object."""
        self.name: TeamColor = name
        self.resources: dict[str, int] = {"wood": 0, "gold": 0}
        self.bases: list[Base] = []
        self.barracks: list[Barracks] = []
        self.houses: list[House] = []
        self.mage_towers: list[MageTower] = []
        self.towers: list[Tower] = []
        self.peasents: list[Peasant] = []
        self.knights: list[Knight] = []
        self.archers: list[Archer] = []
        self.mages: list[Mage] = []

    @property
    def all_entities(self) -> list[Entity]:
        """Return all entities owned by the team."""
        all_ents: list[Entity] = []
        all_ents.extend(self.bases)
        all_ents.extend(self.barracks)
        all_ents.extend(self.houses)
        all_ents.extend(self.mage_towers)
        all_ents.extend(self.towers)
        all_ents.extend(self.peasents)
        all_ents.extend(self.knights)
        all_ents.extend(self.archers)
        all_ents.extend(self.mages)
        return all_ents


class ResourcesGroup:
    """Store neutral resource nodes available on the map.

    Resources are normal entities for drawing/selection/collision, but their
    lifetime differs from units: they disappear when ``amount`` reaches zero
    rather than when ``life`` reaches zero.
    """

    def __init__(self) -> None:
        """Initialize the object."""
        self.golds: list[Gold] = []
        self.woods: list[Wood] = []


@dataclass
class GameState:
    """Core simulation state shared by the manager and all systems."""

    terrain: TerrainMap
    fog: FogOfWar
    map_width: int
    map_height: int
    entities: dict[TeamColor, EntitiesGroup] = field(default_factory=dict)
    resources: ResourcesGroup = field(default_factory=ResourcesGroup)
    current_team: TeamColor = TeamColor.BLUE
    selected_entities: list[Entity] = field(default_factory=list)
    game_over_message: str | None = None
    paused: bool = False

    @property
    def all_entities(self) -> list[Entity]:
        """Return all active entities, including units, buildings, and resources."""
        ents = [entity for group in self.entities.values() for entity in group.all_entities]
        ents.extend(self.resources.woods)
        ents.extend(self.resources.golds)
        return ents

    def clamp_to_world(self, pos: tuple[float, float]) -> tuple[int, int]:
        """Clamp a world-space point to full map bounds (not the viewport)."""
        x, y = clamp_point(pos, min_x=0, max_x=self.map_width, min_y=0, max_y=self.map_height)
        return int(x), int(y)

    def count_units(self, team: TeamColor) -> int:
        """Return the number of living units owned by a team."""
        group = self.entities.get(team)
        if group is None:
            return 0
        return len(group.peasents) + len(group.knights) + len(group.archers) + len(group.mages)

    def population_cap_for_team(self, team: TeamColor) -> int:
        """Return the current population cap for a team from completed buildings."""
        group = self.entities.get(team)
        if group is None or team == TeamColor.RESOURCES:
            return 0

        population_cap = 0
        for building in (*group.bases, *group.barracks, *group.houses, *group.mage_towers, *group.towers):
            if building.life <= 0 or building.is_under_construction:
                continue
            try:
                spec = get_building_spec(getattr(building, "spec_key", type(building).__name__.lower()))
            except ValueError:
                continue
            population_cap += spec.provides_population
        return population_cap
