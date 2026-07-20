"""Readable golden replay for the simultaneous public environment contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from rts_nano.actions import CastAction, MoveAction
from rts_nano.env import RtsNanoEnv
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings

GOLDEN_PATH = Path(__file__).parent / "golden" / "joint_environment_replay_v1.json"


def _settings() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "base": [[40, 40]],
            "mage": [[130, 150]],
            "knight": [[150, 180]],
        },
        "Red": {
            "faction_id": "RUST",
            "base": [[430, 260]],
            "mage": [[260, 150]],
            "knight": [[200, 150]],
        },
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 500,
            "height": 320,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def run_joint_environment_replay() -> dict[str, object]:
    """Run two readable joint decisions and return stable tactical checkpoints."""
    env = RtsNanoEnv(settings=_settings(), max_episode_frames=20)
    manager = env._require_simulation().manager
    assert manager.upgrades.complete(TeamColor.BLUE, "aegis_mage_arcbinder")
    assert manager.upgrades.complete(TeamColor.RED, "rust_mage_plaguecaller")
    initial = env.observe()
    ids = {(entity.kind, entity.team): entity.id for entity in initial.entities if entity.team is not None}
    commands: list[dict[str, object]] = []

    cast_result = env.step_joint(
        {
            TeamColor.BLUE: (
                CastAction(
                    TeamColor.BLUE,
                    ids[("Mage", "Blue")],
                    "arc_bind",
                    target_id=ids[("Knight", "Red")],
                ),
            ),
            TeamColor.RED: (
                CastAction(
                    TeamColor.RED,
                    ids[("Mage", "Red")],
                    "toxic_cloud",
                    destination=(150, 180),
                ),
            ),
        }
    )
    commands.append(
        {
            "decision": 1,
            "blue": "cast arc_bind: Blue Mage -> Red Knight",
            "red": "cast toxic_cloud: Red Mage -> [150, 180]",
            "outcomes": [
                {"team": item.team, "kind": item.kind, "accepted": item.accepted, "reason": item.reason}
                for item in cast_result.action_outcomes
            ],
        }
    )

    move_result = env.step_joint(
        {
            TeamColor.RED: (MoveAction(TeamColor.RED, (300, 220), (ids[("Knight", "Red")],)),),
            TeamColor.BLUE: (MoveAction(TeamColor.BLUE, (100, 220), (ids[("Knight", "Blue")],)),),
        }
    )
    commands.append(
        {
            "decision": 2,
            "blue": "move Blue Knight -> [100, 220]",
            "red": "move Red Knight -> [300, 220]",
            "outcomes": [
                {"team": item.team, "kind": item.kind, "accepted": item.accepted, "reason": item.reason}
                for item in move_result.action_outcomes
            ],
        }
    )

    manager = env._require_simulation().manager
    units = {
        f"{team.value.lower()}_{content_id}": {
            "energy": getattr(entity, "energy", None),
            "cooldowns": dict(sorted(getattr(entity, "ability_cooldowns", {}).items())),
            "arc_mark_remaining": entity.arc_mark_remaining_frames,
            "poison_remaining": entity.poison_remaining_frames,
            "order": entity.current_order.kind if entity.current_order is not None else None,
        }
        for team in (TeamColor.BLUE, TeamColor.RED)
        for content_id in ("mage", "knight")
        for entity in manager.state.entities_by_content_id(content_id, team=team)
    }
    payload: dict[str, object] = {
        "schema_version": 1,
        "observation_schema_version": move_result.observation.schema_version,
        "commands": commands,
        "final": {
            "tick": move_result.observation.tick,
            "terminated": move_result.terminated,
            "truncated": move_result.truncated,
            "completed_upgrades": {
                team.value: [str(item) for item in manager.teams[team].completed_upgrades]
                for team in (TeamColor.BLUE, TeamColor.RED)
            },
            "units": units,
        },
    }
    env.close()
    return payload


def test_joint_environment_replay_matches_readable_golden() -> None:
    expected = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

    assert run_joint_environment_replay() == expected


def test_joint_environment_replay_is_repeatable() -> None:
    assert run_joint_environment_replay() == run_joint_environment_replay()
