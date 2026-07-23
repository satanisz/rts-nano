"""Deterministic 3x3 command-card model shared by Pygame input and rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from rts_nano.content import CONTENT
from rts_nano.game.constants import BOTTOM_MENU_HEIGHT
from rts_nano.simulation.entities.base import Building, Entity, Unit
from rts_nano.simulation.entities.units import CasterUnit, Peasant

if TYPE_CHECKING:
    from rts_nano.application import GameSession

COMMAND_CARD_WIDTH = 180
CMD_COLS = 3
CMD_ROWS = 3
CMD_BTN_SIZE = 46
CMD_PADDING = 6
CMD_SLOTS = CMD_COLS * CMD_ROWS

_BUILD_HOTKEYS = ("Q", "W", "E", "R", "T", "Y", "U", "I")
_ROLE_ORDER = {"population": 0, "military_production": 1, "advanced_production": 2, "defense": 3}


@dataclass(frozen=True, slots=True)
class CommandButton:
    """One command-card button including visual and interaction metadata."""

    rect: pygame.Rect
    label: str
    enabled: bool
    action: str | None
    slot: int = 0
    icon: str = "generic"
    hotkey: str | None = None
    tooltip: str = ""
    cost: str | None = None
    status: str | None = None
    producer: Building | None = None
    building_type: str | None = None
    unit_type: str | None = None
    upgrade_id: str | None = None
    ability_id: str | None = None


@dataclass(frozen=True, slots=True)
class _RawCommand:
    slot: int
    label: str
    enabled: bool
    action: str | None
    icon: str
    hotkey: str | None = None
    tooltip: str = ""
    cost: str | None = None
    status: str | None = None
    producer: Building | None = None
    type_arg: str | None = None


def format_cost(cost: object) -> str:
    """Return a compact resource cost label such as ``220W 60G``."""
    wood = getattr(cost, "wood", 0)
    gold = getattr(cost, "gold", 0)
    parts: list[str] = []
    if wood:
        parts.append(f"{wood}W")
    if gold:
        parts.append(f"{gold}G")
    return " ".join(parts) if parts else "Free"


def _reason_label(reason: str | None) -> str | None:
    return {
        "insufficient_resources": "Not enough resources",
        "population_cap": "Population cap reached",
        "missing_tech": "Requires prerequisite building",
        "missing_building": "Requires prerequisite building",
        "missing_upgrade": "Requires earlier research",
        "already_completed": "Completed",
        "exclusive_choice_completed": "Alternative doctrine chosen",
        "already_reserved": "Queued",
        "exclusive_choice_reserved": "Alternative doctrine queued",
        "wrong_production_building": "Wrong production building",
        "wrong_research_building": "Wrong research building",
        "inactive_building": "Building is inactive",
    }.get(reason, "Unavailable" if reason else None)


class CommandPanel:
    """Build a stable RTS-style command card for the current selection."""

    def __init__(self) -> None:
        """Initialize the root page without binding it to a selection."""
        self._page = "root"
        self._owner: Entity | None = None

    @property
    def page(self) -> str:
        """Return the visible command-card page for tests and input routing."""
        return self._page

    def reset(self) -> None:
        """Return to the root card after a match or selection context change."""
        self._page = "root"
        self._owner = None

    def show_build_menu(self, manager: GameSession) -> bool:
        """Open the registry-derived construction page for a selected Peasant."""
        self._sync_owner(manager)
        if not isinstance(self._owner, Peasant) or self._owner.team != manager.current_team:
            return False
        self._page = "build"
        return True

    def show_root(self) -> None:
        """Return from a submenu to the unit/building root card."""
        self._page = "root"

    def slot_rects(self, screen_width: int, screen_height: int) -> list[pygame.Rect]:
        """Return the nine command-grid slot rectangles for the current viewport."""
        start_x = screen_width - COMMAND_CARD_WIDTH + 12
        start_y = screen_height - BOTTOM_MENU_HEIGHT + 10
        return [
            pygame.Rect(
                start_x + (index % CMD_COLS) * (CMD_BTN_SIZE + CMD_PADDING),
                start_y + (index // CMD_COLS) * (CMD_BTN_SIZE + CMD_PADDING),
                CMD_BTN_SIZE,
                CMD_BTN_SIZE,
            )
            for index in range(CMD_SLOTS)
        ]

    def build(self, manager: GameSession, screen_width: int, screen_height: int) -> list[CommandButton]:
        """Return buttons in slot order; empty slots are intentionally omitted."""
        self._sync_owner(manager)
        if self._owner is None:
            return []
        if self._page == "build" and isinstance(self._owner, Peasant):
            commands = self._construction_commands(manager)
        else:
            self._page = "root"
            commands = self._root_commands(manager)
        rects = self.slot_rects(screen_width, screen_height)
        return [
            self._to_button(command, rects[command.slot]) for command in sorted(commands, key=lambda item: item.slot)
        ]

    def button_for_hotkey(self, manager: GameSession, key_name: str) -> CommandButton | None:
        """Resolve a visible hotkey through the same model used for clicking."""
        normalized = key_name.upper()
        return next(
            (
                button
                for button in self.build(manager, manager.screen_width, manager.screen_height)
                if button.hotkey == normalized
            ),
            None,
        )

    def _sync_owner(self, manager: GameSession) -> None:
        owner = manager.selected_entities[0] if manager.selected_entities else None
        if owner is not self._owner:
            self._owner = owner
            self._page = "root"

    @staticmethod
    def _to_button(command: _RawCommand, rect: pygame.Rect) -> CommandButton:
        values: dict[str, object] = {}
        if command.action == "produce":
            values["unit_type"] = command.type_arg
        elif command.action == "construct":
            values["building_type"] = command.type_arg
        elif command.action == "research":
            values["upgrade_id"] = command.type_arg
        elif command.action == "cast":
            values["ability_id"] = command.type_arg
        return CommandButton(
            rect=rect,
            label=command.label,
            enabled=command.enabled,
            action=command.action,
            slot=command.slot,
            icon=command.icon,
            hotkey=command.hotkey,
            tooltip=command.tooltip,
            cost=command.cost,
            status=command.status,
            producer=command.producer,
            **values,  # type: ignore[arg-type]
        )

    def _root_commands(self, manager: GameSession) -> list[_RawCommand]:
        primary = self._owner
        if isinstance(primary, Unit) and primary.team == manager.current_team:
            return self._unit_commands(manager, primary)
        if isinstance(primary, Building) and primary.team == manager.current_team:
            return self._building_commands(manager, primary)
        return []

    def _unit_commands(self, manager: GameSession, primary: Unit) -> list[_RawCommand]:
        selected = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
        commands = [
            _RawCommand(0, "Move", True, "move", "move", "M", "Move selected units to a target point."),
            _RawCommand(1, "Stop", True, "stop", "stop", "S", "Cancel orders and stop immediately."),
            _RawCommand(2, "Hold", True, "hold", "hold", "H", "Hold position and do not pursue enemies."),
        ]
        if any(entity.attack_damage > 0 for entity in selected):
            commands.extend(
                (
                    _RawCommand(3, "Attack", True, "attack_move", "attack_move", "A", "Attack-move to a point."),
                    _RawCommand(
                        4, "Patrol", True, "patrol", "patrol", "T", "Patrol between the current position and a point."
                    ),
                )
            )
        if any(isinstance(entity, Peasant) for entity in selected):
            commands.append(_RawCommand(5, "Gather", True, "gather", "gather", "G", "Choose Wood or Gold to gather."))
            commands.append(
                _RawCommand(7, "Build", True, "open_build_menu", "build", "B", "Open construction commands.")
            )
        if any(isinstance(entity, Peasant) and (entity.carry_wood > 0 or entity.carry_gold > 0) for entity in selected):
            commands.append(
                _RawCommand(
                    6, "Return", True, "return_cargo", "return_cargo", "C", "Return carried resources to a Base."
                )
            )
        if isinstance(primary, CasterUnit):
            used_slots = {command.slot for command in commands}
            free_slots = [slot for slot in range(CMD_SLOTS) if slot not in used_slots]
            for slot, ability in zip(free_slots, manager.abilities.available_abilities(primary), strict=False):
                cooldown = primary.ability_cooldowns.get(str(ability.id), 0)
                enabled = cooldown == 0 and primary.energy >= ability.energy_cost
                status = f"Cooldown: {cooldown}" if cooldown else None
                if primary.energy < ability.energy_cost:
                    status = f"Need {ability.energy_cost} Energy"
                commands.append(
                    _RawCommand(
                        slot,
                        ability.display_name,
                        enabled,
                        "cast",
                        "ability",
                        tooltip=ability.description,
                        cost=f"{ability.energy_cost} Energy",
                        status=status,
                        type_arg=str(ability.id),
                    )
                )
        return commands

    def _construction_commands(self, manager: GameSession) -> list[_RawCommand]:
        faction = manager.state.faction_for_team(manager.current_team)
        definitions = sorted(
            (definition for definition in CONTENT.buildings_for_faction(faction).values() if definition.constructable),
            key=lambda definition: (_ROLE_ORDER.get(definition.role, 99), str(definition.id)),
        )
        commands: list[_RawCommand] = []
        for slot, (hotkey, definition) in enumerate(zip(_BUILD_HOTKEYS, definitions, strict=False)):
            content_id = str(definition.id)
            enabled, reason = manager.construction.can_team_construct(manager.current_team, content_id)
            requirements = [CONTENT.get_building(str(item)).display_name for item in definition.requires]
            tooltip = definition.display_name
            if requirements:
                tooltip += f"\nRequires: {', '.join(requirements)}"
            commands.append(
                _RawCommand(
                    slot,
                    definition.display_name,
                    enabled,
                    "construct",
                    "building",
                    hotkey,
                    tooltip,
                    format_cost(definition.cost),
                    _reason_label(reason),
                    type_arg=content_id,
                )
            )
        commands.append(_RawCommand(8, "Back", True, "close_submenu", "back", "ESC", "Return to unit commands."))
        return commands

    def _building_commands(self, manager: GameSession, producer: Building) -> list[_RawCommand]:
        try:
            definition = CONTENT.get_building(str(producer.content_id))
        except ValueError:
            return []
        if producer.is_under_construction:
            return [
                _RawCommand(
                    0,
                    "Building",
                    False,
                    None,
                    "build",
                    status=f"{producer.construction_progress:.0%}",
                ),
                _RawCommand(
                    8, "Cancel", True, "cancel_construction", "cancel", "X", "Cancel construction.", producer=producer
                ),
            ]

        commands: list[_RawCommand] = []
        for unit_type in definition.produces:
            unit = CONTENT.get_unit(unit_type)
            enabled, reason = manager.production.can_enqueue_unit(producer, unit_type)
            commands.append(
                _RawCommand(
                    len(commands),
                    unit.display_name,
                    enabled,
                    "produce",
                    "unit",
                    _BUILD_HOTKEYS[len(commands)] if len(commands) < len(_BUILD_HOTKEYS) else None,
                    tooltip=f"Train {unit.display_name}.",
                    cost=format_cost(unit.cost),
                    status=_reason_label(reason),
                    producer=producer,
                    type_arg=unit_type,
                )
            )

        faction = manager.state.faction_for_team(manager.current_team)
        for upgrade in CONTENT.upgrades.values():
            if upgrade.faction != faction or definition.id not in upgrade.research_at:
                continue
            enabled, reason = manager.can_research(producer, str(upgrade.id))
            commands.append(
                _RawCommand(
                    len(commands),
                    upgrade.display_name,
                    enabled,
                    "research",
                    "research",
                    _BUILD_HOTKEYS[len(commands)] if len(commands) < len(_BUILD_HOTKEYS) else None,
                    tooltip=upgrade.description,
                    cost=format_cost(upgrade.cost),
                    status=_reason_label(reason),
                    producer=producer,
                    type_arg=str(upgrade.id),
                )
            )

        queue = manager.production.queue_for(producer)
        if queue:
            active = queue[0]
            name = (
                CONTENT.get_unit(active.content_id).display_name
                if active.kind == "unit"
                else CONTENT.get_upgrade(active.content_id).display_name
            )
            commands = [command for command in commands if command.slot < 8]
            commands.append(
                _RawCommand(
                    8,
                    "Cancel",
                    True,
                    "cancel",
                    "cancel",
                    "X",
                    f"Cancel active activity: {name}.",
                    status=f"{name} {active.progress:.0%}",
                    producer=producer,
                )
            )
        return [command for command in commands if command.slot < CMD_SLOTS]
