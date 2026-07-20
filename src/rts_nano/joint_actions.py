"""Pre-step normalization, validation, and bounded claims for simultaneous actions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from rts_nano.actions import BuildAction, ConstructAction, NoOpAction, ResearchAction
from rts_nano.content import CONTENT
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from collections.abc import Mapping

    from rts_nano.action_translation import ActionTranslator
    from rts_nano.actions import Action
    from rts_nano.application import GameSession

MAX_COMMANDS_PER_TEAM = 16


@dataclass(slots=True)
class PreparedAction:
    """One normalized command plus its pre-step validation result."""

    index: int
    team: TeamColor
    action: Action
    kind: str
    accepted: bool
    reason: str | None = None


def prepare_joint_actions(
    manager: GameSession,
    translator: ActionTranslator,
    actions: Mapping[TeamColor | str, tuple[Action, ...]],
) -> list[PreparedAction]:
    """Return stable actions validated against one state and bounded claim ledger."""
    normalized = _normalize(actions)
    wood = {team: state.resources["wood"] for team, state in manager.teams.items()}
    gold = {team: state.resources["gold"] for team, state in manager.teams.items()}
    reserved_upgrades = {
        team: {str(upgrade_id) for upgrade_id in state.reserved_upgrades} for team, state in manager.teams.items()
    }
    reserved_groups = {
        team: {
            str(CONTENT.get_upgrade(str(upgrade_id)).exclusive_group)
            for upgrade_id in state.reserved_upgrades
            if CONTENT.get_upgrade(str(upgrade_id)).exclusive_group is not None
        }
        for team, state in manager.teams.items()
    }
    prepared: list[PreparedAction] = []
    for team in (TeamColor.BLUE, TeamColor.RED):
        for index, action in enumerate(normalized.get(team, ())):
            item = PreparedAction(index, team, action, _action_kind(action), accepted=False)
            if index >= MAX_COMMANDS_PER_TEAM:
                item.reason = "batch_limit"
            elif getattr(action, "frames", 1) != 1:
                item.reason = "invalid_frames"
            elif not isinstance(action, NoOpAction) and getattr(action, "team", None) != team:
                item.reason = "team_mismatch"
            else:
                valid, reason = translator.validate(action)
                item.accepted = valid
                item.reason = reason
                if valid:
                    _reserve_cost(item, wood, gold, reserved_upgrades, reserved_groups)
            prepared.append(item)
    _resolve_placement_conflicts(prepared)
    return prepared


def _normalize(
    actions: Mapping[TeamColor | str, tuple[Action, ...]],
) -> dict[TeamColor, tuple[Action, ...]]:
    result: dict[TeamColor, tuple[Action, ...]] = {}
    for key, batch in actions.items():
        try:
            team = key if isinstance(key, TeamColor) else TeamColor(key)
        except ValueError as exc:
            raise ValueError(f"Unknown joint-action team: {key}") from exc
        if team not in {TeamColor.BLUE, TeamColor.RED}:
            raise ValueError(f"Unsupported joint-action team: {team.value}")
        if team in result:
            raise ValueError(f"Duplicate joint-action team: {team.value}")
        result[team] = tuple(batch)
    return result


def _reserve_cost(
    item: PreparedAction,
    wood: dict[TeamColor, int],
    gold: dict[TeamColor, int],
    reserved_upgrades: dict[TeamColor, set[str]],
    reserved_groups: dict[TeamColor, set[str]],
) -> None:
    if isinstance(item.action, BuildAction):
        definition = CONTENT.get_unit(item.action.unit_type)
    elif isinstance(item.action, ConstructAction):
        definition = CONTENT.get_building(item.action.building_type)
    elif isinstance(item.action, ResearchAction):
        definition = CONTENT.get_upgrade(item.action.upgrade_id)
        group = str(definition.exclusive_group) if definition.exclusive_group is not None else None
        if item.action.upgrade_id in reserved_upgrades[item.team]:
            item.accepted = False
            item.reason = "upgrade_reserved"
            return
        if group is not None and group in reserved_groups[item.team]:
            item.accepted = False
            item.reason = "exclusive_choice_reserved"
            return
    else:
        return
    if wood[item.team] < definition.cost.wood or gold[item.team] < definition.cost.gold:
        item.accepted = False
        item.reason = "insufficient_reserved_resources"
        return
    wood[item.team] -= definition.cost.wood
    gold[item.team] -= definition.cost.gold
    if isinstance(item.action, ResearchAction):
        research = CONTENT.get_upgrade(item.action.upgrade_id)
        reserved_upgrades[item.team].add(item.action.upgrade_id)
        if research.exclusive_group is not None:
            reserved_groups[item.team].add(str(research.exclusive_group))


def _resolve_placement_conflicts(prepared: list[PreparedAction]) -> None:
    placements = [item for item in prepared if item.accepted and isinstance(item.action, ConstructAction)]
    for position, current in enumerate(placements):
        if not current.accepted:
            continue
        current_action = cast("ConstructAction", current.action)
        current_definition = CONTENT.get_building(current_action.building_type)
        for other in placements[position + 1 :]:
            if not other.accepted:
                continue
            other_action = cast("ConstructAction", other.action)
            other_definition = CONTENT.get_building(other_action.building_type)
            dx = current_action.position[0] - other_action.position[0]
            dy = current_action.position[1] - other_action.position[1]
            if dx * dx + dy * dy >= (current_definition.radius + other_definition.radius) ** 2:
                continue
            if current.team != other.team:
                current.accepted = False
                current.reason = "joint_conflict"
            other.accepted = False
            other.reason = "joint_conflict" if current.team != other.team else "placement_reserved"


def _action_kind(action: Action) -> str:
    name = type(action).__name__.removesuffix("Action")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
