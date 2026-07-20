"""Typed building activity queue and research lifecycle tests."""

from __future__ import annotations

from rts_nano.content import (
    BUILDING_DEFINITIONS,
    FACTION_DEFINITIONS,
    RESOURCE_DEFINITIONS,
    UNIT_DEFINITIONS,
    ContentRegistry,
    ResourceCost,
    UpgradeDefinition,
)
from rts_nano.game.production import ProductionSystem
from rts_nano.game.types import ContentId, FactionId, UpgradeId
from rts_nano.game.upgrades import UpgradeSystem
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities import TeamColor
from rts_nano.simulation.entities.base import Building


def _upgrade(upgrade_id: str, faction: str, building_id: str) -> UpgradeDefinition:
    return UpgradeDefinition(
        id=UpgradeId(upgrade_id),
        display_name=upgrade_id.replace("_", " ").title(),
        description="Test research queue upgrade.",
        faction=FactionId(faction),
        research_at=(ContentId(building_id),),
        cost=ResourceCost(wood=40, gold=20),
        research_frames=5,
        affected_content=(ContentId("knight"),),
    )


def _systems() -> tuple[HeadlessSimulation, ContentRegistry, UpgradeSystem, ProductionSystem]:
    aegis = _upgrade("aegis_test", "AEGIS", "arsenal")
    rust = _upgrade("rust_test", "RUST", "pit")
    registry = ContentRegistry(
        units=UNIT_DEFINITIONS,
        buildings=BUILDING_DEFINITIONS,
        resources=RESOURCE_DEFINITIONS,
        factions=FACTION_DEFINITIONS,
        upgrades=(aegis, rust),
    )
    simulation = HeadlessSimulation.from_settings(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[100, 100]], "arsenal": [[220, 100]]},
            "Red": {"faction_id": "RUST", "base": [[700, 500]], "pit": [[580, 500]]},
            "Resources": {"wood": [], "gold": []},
            "Terrain": {
                "width": 800,
                "height": 600,
                "high_ground": [],
                "water": [],
                "ramps": [],
                "rocks": [],
                "grass": [],
            },
        }
    )
    upgrades = UpgradeSystem(simulation.manager.state, registry)
    activities = ProductionSystem(simulation.manager.state, upgrades, registry)
    for team_state in simulation.manager.teams.values():
        team_state.resources.update({"wood": 1000, "gold": 1000})
    return simulation, registry, upgrades, activities


def _building(simulation: HeadlessSimulation, content_id: str, team: TeamColor) -> Building:
    entity = simulation.manager.state.entities_by_content_id(content_id, team=team)[0]
    assert isinstance(entity, Building)
    return entity


def test_unit_and_research_share_one_sequential_activity_queue() -> None:
    """Research waits behind training and then completes through UpgradeSystem."""
    simulation, registry, _, activities = _systems()
    arsenal = _building(simulation, "arsenal", TeamColor.BLUE)

    assert activities.enqueue_unit(arsenal, "knight")
    assert activities.enqueue_research(arsenal, "aegis_test")
    queue = activities.queue_for(arsenal)
    assert [item.kind for item in queue] == ["unit", "research"]
    research_remaining = queue[1].remaining_frames

    activities.update()
    assert activities.queue_for(arsenal)[1].remaining_frames == research_remaining
    for _ in range(registry.get_unit("knight").production_frames - 1):
        activities.update()
    assert [item.kind for item in activities.queue_for(arsenal)] == ["research"]
    for _ in range(registry.get_upgrade("aegis_test").research_frames):
        activities.update()

    assert simulation.manager.teams[TeamColor.BLUE].has_upgrade("aegis_test")
    assert not activities.queue_for(arsenal)
    simulation.close()


def test_research_cancel_refunds_and_releases_reservation() -> None:
    """Player cancellation refunds 75%, while making the choice available again."""
    simulation, _, _, activities = _systems()
    arsenal = _building(simulation, "arsenal", TeamColor.BLUE)
    team_state = simulation.manager.teams[TeamColor.BLUE]
    before = dict(team_state.resources)

    assert activities.enqueue_research(arsenal, "aegis_test")
    assert [str(item) for item in team_state.reserved_upgrades] == ["aegis_test"]
    assert activities.cancel_next(arsenal)

    assert team_state.resources == {"wood": before["wood"] - 10, "gold": before["gold"] - 5}
    assert team_state.reserved_upgrades == []
    assert activities.can_research(arsenal, "aegis_test") == (True, None)
    simulation.close()


def test_destroyed_researcher_releases_without_refund() -> None:
    """Building destruction loses its paid job but cannot lock the choice forever."""
    simulation, _, _, activities = _systems()
    arsenal = _building(simulation, "arsenal", TeamColor.BLUE)
    team_state = simulation.manager.teams[TeamColor.BLUE]

    assert activities.enqueue_research(arsenal, "aegis_test")
    paid_resources = dict(team_state.resources)
    arsenal.life = 0
    activities.update()

    assert team_state.resources == paid_resources
    assert team_state.reserved_upgrades == []
    assert not activities.queue_for(arsenal)
    simulation.close()


def test_two_teams_research_independently_and_restart_is_clean() -> None:
    """Reservations and completion are team-local; a restarted match has neither."""
    simulation, registry, _, activities = _systems()
    arsenal = _building(simulation, "arsenal", TeamColor.BLUE)
    pit = _building(simulation, "pit", TeamColor.RED)
    assert activities.enqueue_research(arsenal, "aegis_test")
    assert activities.enqueue_research(pit, "rust_test")

    for _ in range(max(item.research_frames for item in registry.upgrades.values())):
        activities.update()

    assert simulation.manager.teams[TeamColor.BLUE].has_upgrade("aegis_test")
    assert simulation.manager.teams[TeamColor.RED].has_upgrade("rust_test")
    restarted = simulation.manager.restart()
    assert all(not state.completed_upgrades and not state.reserved_upgrades for state in restarted.teams.values())
    simulation.close()
