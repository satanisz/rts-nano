"""C4 regression for the Ashen Circuit worker/base exit found by macro acceptance."""

from __future__ import annotations

from rts_nano.application import GameSession
from rts_nano.simulation.entities import TeamColor


def _session() -> GameSession:
    return GameSession(
        {
            "schema_version": 2,
            "Blue": {"faction_id": "AEGIS", "base": [[80, 80]], "peasant": []},
            "Red": {
                "faction_id": "RUST",
                "base": [[1360, 250]],
                "house": [[1440, 250]],
                "pit": [[1280, 250]],
                "chem_vat": [[1360, 330]],
                "peasant": [[1349, 278]],
            },
            "Resources": {"gold": [[1383, 382]], "wood": []},
            "Terrain": {
                "width": 1600,
                "height": 1100,
                "water": [],
                "rocks": [],
                "ramps": [],
                "high_ground": [],
                "grass": [],
            },
        }
    )


def test_worker_leaves_base_overlap_and_completes_a_gather_deposit_cycle() -> None:
    game = _session()
    worker = game.units_for_team(TeamColor.RED)[0]
    gold = game.state.resources_by_content("gold")[0]

    assert game.issue_gather_order(TeamColor.RED, gold, [worker]) == 1
    assert worker.path
    for _ in range(2000):
        game.update()
        if game.teams[TeamColor.RED].resources["gold"] >= 10:
            break

    assert game.teams[TeamColor.RED].resources["gold"] >= 10
    assert gold.amount < 100
    assert not worker.path_unreachable


def test_overlap_escape_cannot_cross_deeper_through_a_building() -> None:
    game = _session()
    worker = game.units_for_team(TeamColor.RED)[0]
    start = worker.get_center()
    # The old endpoint-only check accepted this edge although its first step
    # approached the base center and the local movement validator rejected it.
    assert game.movement._building_blocks_segment(worker, start, (1392, 272), None)
    assert not game.movement._building_blocks_segment(worker, start, (1328, 272), None)
