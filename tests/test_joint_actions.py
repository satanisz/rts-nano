"""Simultaneous multi-team environment decision tests."""

from __future__ import annotations

from rts_nano.actions import BuildAction, ConstructAction, MoveAction, NoOpAction
from rts_nano.env import RtsNanoEnv
from rts_nano.simulation.entities import TeamColor


def _settings() -> dict[str, object]:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "base": [[100, 100]],
            "peasant": [[180, 180]],
        },
        "Red": {
            "faction_id": "RUST",
            "base": [[700, 500]],
            "peasant": [[620, 420]],
        },
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


def _id(env: RtsNanoEnv, kind: str, team: str) -> str:
    return next(entity.id for entity in env.observe().entities if entity.kind == kind and entity.team == team)


def test_joint_step_applies_both_teams_before_one_time_advance() -> None:
    env = RtsNanoEnv(settings=_settings(), frame_skip=4)
    blue_worker = _id(env, "Peasant", "Blue")
    red_worker = _id(env, "Peasant", "Red")
    result = env.step_joint(
        {
            TeamColor.BLUE: (MoveAction(TeamColor.BLUE, (300, 200), (blue_worker,)),),
            TeamColor.RED: (MoveAction(TeamColor.RED, (500, 400), (red_worker,)),),
        }
    )

    assert result.observation.tick == 4
    assert result.info["decision_count"] == 1
    assert len(result.action_outcomes) == 2
    assert all(outcome.accepted for outcome in result.action_outcomes)
    assert result.rewards == {"Blue": 0.0, "Red": 0.0}
    env.close()


def test_joint_mapping_order_does_not_change_result() -> None:
    first = RtsNanoEnv(settings=_settings(), frame_skip=5)
    second = RtsNanoEnv(settings=_settings(), frame_skip=5)
    first_actions = {
        TeamColor.BLUE: (MoveAction(TeamColor.BLUE, (300, 200), (_id(first, "Peasant", "Blue"),)),),
        TeamColor.RED: (MoveAction(TeamColor.RED, (500, 400), (_id(first, "Peasant", "Red"),)),),
    }
    second_actions = {
        TeamColor.RED: (MoveAction(TeamColor.RED, (500, 400), (_id(second, "Peasant", "Red"),)),),
        TeamColor.BLUE: (MoveAction(TeamColor.BLUE, (300, 200), (_id(second, "Peasant", "Blue"),)),),
    }

    first_result = first.step_joint(first_actions)
    second_result = second.step_joint(second_actions)
    assert first_result.observation.to_dict() == second_result.observation.to_dict()
    assert first_result.action_outcomes == second_result.action_outcomes
    first.close()
    second.close()


def test_invalid_command_is_noop_while_independent_command_executes() -> None:
    env = RtsNanoEnv(settings=_settings())
    red_worker = _id(env, "Peasant", "Red")
    result = env.step_joint(
        {
            TeamColor.BLUE: (MoveAction(TeamColor.RED, (300, 200)),),
            TeamColor.RED: (MoveAction(TeamColor.RED, (500, 400), (red_worker,)),),
        }
    )
    blue, red = result.action_outcomes
    assert not blue.accepted
    assert blue.reason == "team_mismatch"
    assert red.accepted
    env.close()


def test_resource_ledger_rejects_second_overspending_activity() -> None:
    env = RtsNanoEnv(settings=_settings())
    manager = env._require_simulation().manager
    peasant_cost = 50
    manager.teams[TeamColor.BLUE].resources.update({"wood": peasant_cost, "gold": 0})
    base_id = _id(env, "Base", "Blue")
    result = env.step_joint(
        {
            TeamColor.BLUE: (
                BuildAction(TeamColor.BLUE, base_id=base_id, unit_type="peasant"),
                BuildAction(TeamColor.BLUE, base_id=base_id, unit_type="peasant"),
            )
        }
    )

    first, second = result.action_outcomes
    assert first.accepted
    assert not second.accepted
    assert second.reason == "insufficient_reserved_resources"
    assert len(manager.production.queue_for(manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0])) == 1
    env.close()


def test_cross_team_placement_conflict_rejects_both_claims() -> None:
    env = RtsNanoEnv(settings=_settings())
    manager = env._require_simulation().manager
    for team in (TeamColor.BLUE, TeamColor.RED):
        manager.teams[team].resources.update({"wood": 1000, "gold": 1000})
    result = env.step_joint(
        {
            TeamColor.BLUE: (
                ConstructAction(
                    TeamColor.BLUE,
                    (400, 300),
                    builder_id=_id(env, "Peasant", "Blue"),
                    building_type="house",
                ),
            ),
            TeamColor.RED: (
                ConstructAction(
                    TeamColor.RED,
                    (400, 300),
                    builder_id=_id(env, "Peasant", "Red"),
                    building_type="house",
                ),
            ),
        }
    )

    assert all(not outcome.accepted for outcome in result.action_outcomes)
    assert {outcome.reason for outcome in result.action_outcomes} == {"joint_conflict"}
    env.close()


def test_batch_cap_and_fixed_joint_frames_are_reported() -> None:
    env = RtsNanoEnv(settings=_settings())
    actions = (NoOpAction(frames=2),) + tuple(NoOpAction() for _ in range(17))
    result = env.step_joint({TeamColor.BLUE: actions})

    assert len(result.action_outcomes) == 18
    assert result.action_outcomes[0].reason == "invalid_frames"
    assert result.action_outcomes[16].reason == "batch_limit"
    assert result.action_outcomes[17].reason == "batch_limit"
    env.close()


def test_joint_rewards_are_per_team_and_resettable() -> None:
    env = RtsNanoEnv(
        settings=_settings(),
        reward_fns={
            TeamColor.BLUE: lambda observation: float(observation.tick),
            TeamColor.RED: lambda observation: -float(observation.tick),
        },
        frame_skip=3,
    )
    result = env.step_joint({})
    assert result.rewards == {"Blue": 3.0, "Red": -3.0}
    env.close()
