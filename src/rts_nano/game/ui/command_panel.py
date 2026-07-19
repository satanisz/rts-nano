"""Bottom command-panel layout, decoupled from drawing.

This computes the command buttons for the current selection — their label,
enabled state, action, target, and on-screen rectangle — with no rendering. Both
the renderer (which draws the buttons) and the input handler (which hit-tests
them) read the same buttons, so input no longer depends on a draw pass having run
to populate hit-target lists.

Screen dimensions are passed in by the caller because the playable viewport is
dynamic (``GameManager.set_viewport_size`` mutates the screen globals); passing
the current values keeps render and input layouts identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from rts_nano.content import CONTENT
from rts_nano.game.constants import BOTTOM_MENU_HEIGHT
from rts_nano.simulation.entities.base import Building, Unit
from rts_nano.simulation.entities.units import Peasant

if TYPE_CHECKING:
    from rts_nano.application import GameSession

COMMAND_CARD_WIDTH = 180
CMD_COLS = 3
CMD_ROWS = 3
CMD_BTN_SIZE = 46
CMD_PADDING = 6
CMD_SLOTS = CMD_COLS * CMD_ROWS

# Action kinds that map to a selected-unit command button.
_UNIT_COMMAND_ACTIONS = frozenset({"stop", "hold", "attack_move", "patrol", "gather", "return_cargo"})


@dataclass(frozen=True, slots=True)
class CommandButton:
    """One command-panel button: where it is, what it says, and what it does."""

    rect: pygame.Rect
    label: str
    enabled: bool
    action: str | None
    producer: Building | None = None
    building_type: str | None = None
    unit_type: str | None = None


# A raw command before layout: (label, enabled, action, type_argument).
type _RawCommand = tuple[str, bool, str | None, str | None]


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


class CommandPanel:
    """Computes command-panel buttons for the current selection (no drawing)."""

    def slot_rects(self, screen_width: int, screen_height: int) -> list[pygame.Rect]:
        """Return the nine command-grid slot rectangles for the current viewport."""
        command_card_x = screen_width - COMMAND_CARD_WIDTH
        start_x = command_card_x + 12
        start_y = screen_height - BOTTOM_MENU_HEIGHT + 10
        rects: list[pygame.Rect] = []
        for index in range(CMD_SLOTS):
            col = index % CMD_COLS
            row = index // CMD_COLS
            rects.append(
                pygame.Rect(
                    start_x + col * (CMD_BTN_SIZE + CMD_PADDING),
                    start_y + row * (CMD_BTN_SIZE + CMD_PADDING),
                    CMD_BTN_SIZE,
                    CMD_BTN_SIZE,
                )
            )
        return rects

    def build(self, manager: GameSession, screen_width: int, screen_height: int) -> list[CommandButton]:
        """Return the laid-out command buttons for the manager's current selection."""
        commands, producer = self._commands(manager)
        rects = self.slot_rects(screen_width, screen_height)
        buttons: list[CommandButton] = []
        for index, (label, enabled, action, type_arg) in enumerate(commands[:CMD_SLOTS]):
            buttons.append(self._to_button(rects[index], label, enabled, action, type_arg, producer))
        return buttons

    @staticmethod
    def _to_button(
        rect: pygame.Rect,
        label: str,
        enabled: bool,
        action: str | None,
        type_arg: str | None,
        producer: Building | None,
    ) -> CommandButton:
        if action == "produce":
            return CommandButton(rect, label, enabled, action, producer=producer, unit_type=type_arg)
        if action == "construct":
            return CommandButton(rect, label, enabled, action, building_type=type_arg)
        if action in {"cancel", "cancel_construction"}:
            return CommandButton(rect, label, enabled, action, producer=producer)
        return CommandButton(rect, label, enabled, action)

    def _commands(self, manager: GameSession) -> tuple[list[_RawCommand], Building | None]:
        commands: list[_RawCommand] = []
        if not manager.selected_entities:
            return commands, None

        primary_entity = manager.selected_entities[0]
        selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]

        if isinstance(primary_entity, Unit) and primary_entity.team == manager.current_team:
            commands.append(("Stop", True, "stop", None))
            commands.append(("Hold", True, "hold", None))
            if any(entity.attack_damage > 0 for entity in selected_units):
                commands.append(("Attack Move", True, "attack_move", None))
                commands.append(("Patrol", True, "patrol", None))
            if any(isinstance(entity, Peasant) for entity in selected_units):
                commands.append(("Gather", True, "gather", None))
            if any(
                isinstance(entity, Peasant) and (entity.carry_wood > 0 or entity.carry_gold > 0)
                for entity in selected_units
            ):
                commands.append(("Return Cargo", True, "return_cargo", None))

        selected_producer: Building | None = None
        if isinstance(primary_entity, Building) and getattr(primary_entity, "team", None) == manager.current_team:
            selected_producer = primary_entity
            try:
                producer_key = getattr(selected_producer, "spec_key", type(selected_producer).__name__.lower())
                building_spec = CONTENT.get_building(producer_key)
            except ValueError:
                building_spec = None

            if selected_producer.is_under_construction:
                commands.append((f"Build {selected_producer.construction_progress:.0%}", False, None, None))
                commands.append(("Cancel Build", True, "cancel_construction", None))
            elif building_spec is not None and building_spec.produces:
                queue = manager.production.queue_for(selected_producer)
                if queue:
                    active_unit = CONTENT.get_unit(queue[0].unit_type).display_name
                    commands.append((f"{active_unit} {queue[0].progress:.0%}", False, None, None))
                    commands.append(("Cancel", True, "cancel", None))

                for unit_type in building_spec.produces:
                    can_build, reason = manager.production.can_enqueue_unit(selected_producer, unit_type)
                    unit_name = CONTENT.get_unit(unit_type).display_name
                    if can_build:
                        commands.append((f"Train {unit_name}", True, "produce", unit_type))
                    elif reason == "population_cap":
                        commands.append(("Cap Reached", False, None, None))
                    elif reason == "insufficient_resources":
                        commands.append((f"Need {format_cost(CONTENT.get_unit(unit_type).cost)}", False, None, None))
                    else:
                        commands.append(("Unavailable", False, None, None))
        elif isinstance(primary_entity, Peasant) and primary_entity.team == manager.current_team:
            faction = manager.state.faction_for_team(manager.current_team)
            for building_type in manager.construction.supported_building_types():
                try:
                    building_spec = CONTENT.get_building(building_type)
                except ValueError:
                    continue
                if building_spec.faction is not None and building_spec.faction != faction:
                    continue
                can_construct, reason = manager.construction.can_team_construct(manager.current_team, building_type)
                if can_construct:
                    commands.append((f"Build {building_spec.display_name}", True, "construct", building_type))
                elif reason == "insufficient_resources":
                    commands.append((f"Need {format_cost(building_spec.cost)}", False, None, None))
                elif reason == "missing_tech":
                    commands.append((f"Build {building_spec.display_name}", False, None, None))
                else:
                    commands.append(("Unavailable", False, None, None))

        return commands, selected_producer
