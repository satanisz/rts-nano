"""Explicit generic state container for the deterministic game simulation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from rts_nano.content import CONTENT
from rts_nano.game.assets.entities import TeamColor
from rts_nano.game.entity_store import EntityStore
from rts_nano.game.rules import clamp_point
from rts_nano.game.spatial import SpatialIndex
from rts_nano.game.types import EntityCategory, FactionId, TeamId

if TYPE_CHECKING:
    from rts_nano.game.assets.entities.base_entities import Building, Entity, Resource, Unit
    from rts_nano.game.fog import FogOfWar
    from rts_nano.game.terrain import TerrainMap


@dataclass(slots=True)
class TeamState:
    """Economy and explicit faction assignment for one simulation team."""

    team_id: TeamId
    faction_id: FactionId
    resources: dict[str, int] = field(default_factory=lambda: {"wood": 0, "gold": 0})


@dataclass
class GameState:
    """Core simulation state shared by the manager and gameplay systems."""

    terrain: TerrainMap
    fog: FogOfWar
    map_width: int
    map_height: int
    teams: dict[TeamColor, TeamState] = field(default_factory=dict)
    store: EntityStore = field(default_factory=EntityStore)
    current_team: TeamColor = TeamColor.BLUE
    selected_entities: list[Entity] = field(default_factory=list)
    game_over_message: str | None = None
    paused: bool = False
    load_visuals: bool = True
    spatial_index: SpatialIndex = field(default_factory=SpatialIndex)

    @property
    def all_entities(self) -> list[Entity]:
        """Return all active entities in stable creation order."""
        return self.store.all()

    def team(self, team: TeamColor) -> TeamState | None:
        """Return generic team state."""
        return self.teams.get(team)

    def faction_for_team(self, team: TeamColor) -> FactionId:
        """Return the faction explicitly assigned by map setup."""
        team_state = self.teams.get(team)
        if team_state is None:
            raise KeyError(f"Unknown team: {team}")
        return team_state.faction_id

    def entities_for_team(self, team: TeamColor) -> list[Entity]:
        """Return all entities owned by a team."""
        return self.store.for_team(team)

    def units_for_team(self, team: TeamColor) -> list[Unit]:
        """Return all team units through the category index."""
        return cast("list[Unit]", self.store.by_category(EntityCategory.UNIT, team=team))

    def buildings_for_team(self, team: TeamColor) -> list[Building]:
        """Return all team buildings through the category index."""
        return cast("list[Building]", self.store.by_category(EntityCategory.BUILDING, team=team))

    def resources_by_content(self, content_id: str) -> list[Resource]:
        """Return neutral resources of one content type."""
        return cast("list[Resource]", self.store.by_content_id(content_id))

    def entities_by_content_id(self, content_id: str, *, team: TeamColor | None = None) -> list[Entity]:
        """Return entities by canonical content ID."""
        return self.store.by_content_id(content_id, team=team)

    def clamp_to_world(self, pos: tuple[float, float]) -> tuple[int, int]:
        """Clamp a world-space point to full map bounds."""
        x, y = clamp_point(pos, min_x=0, max_x=self.map_width, min_y=0, max_y=self.map_height)
        return int(x), int(y)

    def count_units(self, team: TeamColor) -> int:
        """Return the number of living units owned by a team."""
        return len(self.units_for_team(team))

    def population_cap_for_team(self, team: TeamColor) -> int:
        """Return population supplied by living completed buildings."""
        if team == TeamColor.RESOURCES:
            return 0
        return sum(
            CONTENT.get_building(str(building.content_id)).provides_population
            for building in self.buildings_for_team(team)
            if building.life > 0 and not building.is_under_construction
        )
