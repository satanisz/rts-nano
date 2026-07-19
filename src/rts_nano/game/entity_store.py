"""Stable primary storage and generic indexes for simulation entities."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from rts_nano.game.types import ContentId, EntityCategory, EntityId, TeamId

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rts_nano.game.assets.entities.base_entities import Entity


class EntityStore:
    """Own entities once and expose deterministic secondary-index queries."""

    def __init__(self) -> None:
        """Initialize empty primary and secondary indexes."""
        self._entities: dict[EntityId, Entity] = {}
        self._team_index: dict[TeamId, list[EntityId]] = defaultdict(list)
        self._category_index: dict[EntityCategory, list[EntityId]] = defaultdict(list)
        self._content_index: dict[ContentId, list[EntityId]] = defaultdict(list)
        self._next_id = 1

    def add(self, entity: Entity) -> EntityId:
        """Add an entity once, assign its stable ID, and update all indexes."""
        if getattr(entity, "entity_id", None) is not None:
            raise ValueError("Entity is already registered")
        entity_id = EntityId(self._next_id)
        self._next_id += 1
        entity.entity_id = entity_id
        self._entities[entity_id] = entity
        self._category_index[entity.definition.category].append(entity_id)
        self._content_index[entity.content_id].append(entity_id)
        team = getattr(entity, "team", None)
        if team is not None:
            self._team_index[TeamId(str(getattr(team, "value", team)))].append(entity_id)
        return entity_id

    def remove(self, entity: Entity) -> bool:
        """Remove an entity and all of its index entries."""
        entity_id = getattr(entity, "entity_id", None)
        if entity_id is None or self._entities.pop(entity_id, None) is None:
            return False
        self._category_index[entity.definition.category].remove(entity_id)
        self._content_index[entity.content_id].remove(entity_id)
        team = getattr(entity, "team", None)
        if team is not None:
            self._team_index[TeamId(str(getattr(team, "value", team)))].remove(entity_id)
        return True

    def get(self, entity_id: EntityId) -> Entity:
        """Return one entity by its stable simulation ID."""
        return self._entities[entity_id]

    def all(self) -> list[Entity]:
        """Return entities in stable creation order."""
        return list(self._entities.values())

    def for_team(self, team: object) -> list[Entity]:
        """Return one team's entities in stable creation order."""
        team_id = TeamId(str(getattr(team, "value", team)))
        return [self._entities[entity_id] for entity_id in self._team_index.get(team_id, ())]

    def by_category(self, category: EntityCategory, *, team: object | None = None) -> list[Entity]:
        """Return a category, optionally intersected with one team."""
        entity_ids = self._category_index.get(category, ())
        if team is None:
            return [self._entities[entity_id] for entity_id in entity_ids]
        team_ids = set(self._team_index.get(TeamId(str(getattr(team, "value", team))), ()))
        return [self._entities[entity_id] for entity_id in entity_ids if entity_id in team_ids]

    def by_content_id(self, content_id: str | ContentId, *, team: object | None = None) -> list[Entity]:
        """Return one content type, optionally intersected with one team."""
        entity_ids = self._content_index.get(ContentId(str(content_id)), ())
        if team is None:
            return [self._entities[entity_id] for entity_id in entity_ids]
        team_ids = set(self._team_index.get(TeamId(str(getattr(team, "value", team))), ()))
        return [self._entities[entity_id] for entity_id in entity_ids if entity_id in team_ids]

    def __iter__(self) -> Iterator[Entity]:
        """Iterate in stable creation order."""
        return iter(self._entities.values())

    def __len__(self) -> int:
        """Return the number of registered entities."""
        return len(self._entities)
